#Imports.
import os
import time
import asyncio
import aiohttp
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
import logging
from zoneinfo import ZoneInfo

#Load env.
TWITCH_CLIENT = os.getenv("TWITCH_CLIENT")
TWITCH_SECRET = os.getenv("TWITCH_SECRET")
TWITCH_STREAMER = [s.strip().lower() for s in os.getenv("TWITCH_STREAMER", "").split(",") if s.strip()]
TWITCH_LIVE = int(os.getenv("TWITCH_LIVE", "0"))
TWITCH_POLL = int(os.getenv("TWITCH_POLL", "120"))
CLIP_CHANNEL = int(os.getenv("CLIP_CHANNEL", "0"))
CLIP_POLL = int(os.getenv("CLIP_POLL", "300"))
CLIP_WINDOW_MIN = int(os.getenv("CLIP_WINDOW_MIN", "60"))

#Helix.
HELIX = "https://api.twitch.tv/helix"

#Logger.
log = logging.getLogger("twitch_cog")

#Houston timezone.
HOUSTON_TZ = ZoneInfo("America/Chicago")
DAILY_WINDOWS = [
    ("13:00", "14:00"),  #1pm–2pm.
    ("20:00", "21:00"),  #8pm–9pm.
]

class TwitchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None
        self.token: str | None = None
        self.token_expiry_ts: float = 0.0

        self.live_cache: set[str] = set()
        self.clip_checkpoint: dict[str, datetime] = {}
        self.last_live_started_at: dict[str, str] = {}
        log.info("TwitchCog init. CLIP_CHANNEL=%s STREAMERS=%s", CLIP_CHANNEL, TWITCH_STREAMER)

        #Regular stream check and priority window check.
        self.check_streams.start()
        self.check_streams_priority.start()

        if CLIP_CHANNEL and TWITCH_STREAMER:
            self.check_clips.start()

    #Internals.
    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session and not self.session.closed:
            return self.session
        self.session = aiohttp.ClientSession()
        return self.session

    async def _ensure_token(self):
        if self.token and time.time() < self.token_expiry_ts - 60:
            return
        sess = await self._get_session()
        async with sess.post(
            "https://id.twitch.tv/oauth2/token",
            data={"client_id": TWITCH_CLIENT, "client_secret": TWITCH_SECRET, "grant_type": "client_credentials"},
            timeout=20
        ) as r:
            data = await r.json()
            self.token = data.get("access_token")
            expires_in = int(data.get("expires_in", 3600))
            self.token_expiry_ts = time.time() + expires_in
            log.info("Twitch token refreshed (expires_in=%ss)", expires_in)

    async def _helix_headers(self):
        await self._ensure_token()
        return {"Client-ID": TWITCH_CLIENT, "Authorization": f"Bearer {self.token}"}

    async def _fetch_streams(self, logins: list[str]):
        if not logins:
            return []
        sess = await self._get_session()
        params = [("user_login", u) for u in logins]
        async with sess.get(f"{HELIX}/streams", params=params, headers=await self._helix_headers(), timeout=20) as r:
            data = await r.json()
            return data.get("data", [])

    async def _fetch_users(self, logins: list[str]):
        if not logins:
            return {}
        sess = await self._get_session()
        params = [("login", u) for u in logins]
        async with sess.get(f"{HELIX}/users", params=params, headers=await self._helix_headers(), timeout=20) as r:
            data = await r.json()
            return {u["login"].lower(): u for u in data.get("data", [])}

    async def _fetch_broadcaster_ids(self, logins: list[str]) -> dict[str, str]:
        users = await self._fetch_users(logins)
        return {login: u.get("id") for login, u in users.items() if u.get("id")}

    #Live announcement.
    async def _check_streams_once(self):
        if not (TWITCH_CLIENT and TWITCH_SECRET and TWITCH_LIVE and TWITCH_STREAMER):
            return
        channel = self.bot.get_channel(TWITCH_LIVE)
        if not channel:
            try:
                channel = await self.bot.fetch_channel(TWITCH_LIVE)
            except Exception:
                return
        if not hasattr(channel, "send"):
            return

        try:
            streams = await self._fetch_streams(TWITCH_STREAMER)
            live_now = {s["user_login"].lower(): s for s in streams if s.get("type") == "live"}
            users = await self._fetch_users(list(live_now.keys()))

            for login, stream in live_now.items():
                started_at = stream.get("started_at")
                #Only announce live if it hasn't been announced yet.
                if started_at and self.last_live_started_at.get(login) == started_at:
                    continue

                user = users.get(login) or {"login": login, "display_name": login, "profile_image_url": None}
                await self._announce(channel, stream, user)

                if started_at:
                    self.last_live_started_at[login] = started_at

            self.live_cache = set(live_now.keys())
        except Exception:
            pass

    async def _announce(self, channel, stream, user):
        login = user["login"].lower()
        title = stream.get("title") or "Live on Twitch!"
        game = stream.get("game_name") or "Just Chatting"
        url = f"https://twitch.tv/{login}"

        embed = discord.Embed(
            title=f"{user.get('display_name')} is now LIVE!",
            description=f"**{title}**\nPlaying: {game}\n{url}",
        )
        embed.set_thumbnail(url=user.get("profile_image_url") or discord.Embed.Empty)

        await channel.send(
            content=f"🔴 **{user.get('display_name')}** is live! Come join in and chat! <@&1405373110143684618>",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

    #Window logic.
    def _in_daily_window(self, now_utc: datetime) -> bool:
        """Return True if 'now_utc' is within any DAILY_WINDOWS in America/Chicago."""
        now_local = now_utc.astimezone(HOUSTON_TZ)
        today = now_local.date()
        for start_str, end_str in DAILY_WINDOWS:
            try:
                sh, sm = map(int, start_str.split(":"))
                eh, em = map(int, end_str.split(":"))
            except Exception:
                continue
            start_local = datetime(today.year, today.month, today.day, sh, sm, tzinfo=HOUSTON_TZ)
            end_local = datetime(today.year, today.month, today.day, eh, em, tzinfo=HOUSTON_TZ)
            if start_local <= now_local < end_local:
                return True
        return False

    #Loops.
    @tasks.loop(seconds=TWITCH_POLL)
    async def check_streams(self):
        await self.bot.wait_until_ready()
        await self._check_streams_once()

    @check_streams.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    @tasks.loop(seconds=60)
    async def check_streams_priority(self):
        await self.bot.wait_until_ready()
        now = datetime.now(timezone.utc)
        if self._in_daily_window(now):
            await self._check_streams_once()

    @check_streams_priority.before_loop
    async def before_check_priority(self):
        await self.bot.wait_until_ready()

    #Clips.
    async def _fetch_clips(self, broadcaster_id: str, started_at_iso: str):
        sess = await self._get_session()
        params = {"broadcaster_id": broadcaster_id, "started_at": started_at_iso, "first": 20}
        async with sess.get(f"{HELIX}/clips", params=params, headers=await self._helix_headers(), timeout=20) as r:
            data = await r.json()
            return data.get("data", []) or []

    @tasks.loop(seconds=CLIP_POLL)
    async def check_clips(self):
        await self.bot.wait_until_ready()
        if not (CLIP_CHANNEL and TWITCH_STREAMER and TWITCH_CLIENT and TWITCH_SECRET):
            return

        ch = self.bot.get_channel(CLIP_CHANNEL)
        if not ch:
            try:
                ch = await self.bot.fetch_channel(CLIP_CHANNEL)
            except Exception:
                return

        if isinstance(ch, discord.Thread):
            try:
                if ch.archived:
                    await ch.unarchive()
                if not ch.me:
                    await ch.join()
            except Exception:
                pass

        if not hasattr(ch, "send"):
            return

        try:
            ids = await self._fetch_broadcaster_ids(TWITCH_STREAMER)
            now = datetime.now(timezone.utc)

            for login, bid in ids.items():
                since = self.clip_checkpoint.get(login) or (now - timedelta(minutes=CLIP_WINDOW_MIN))
                started_at_iso = since.isoformat().replace("+00:00", "Z")
                clips = await self._fetch_clips(bid, started_at_iso)

                def parse_ts(c):
                    try:
                        return datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
                    except Exception:
                        return since

                clips.sort(key=parse_ts)
                latest_seen = since

                for clip in clips:
                    created_at = parse_ts(clip)
                    if created_at <= since:
                        continue

                    url = clip.get("url")
                    title = clip.get("title") or "New clip"
                    creator = clip.get("creator_name") or "Someone"
                    thumb = clip.get("thumbnail_url")
                    if thumb and "{width}" in thumb:
                        thumb = thumb.replace("{width}", "1280").replace("{height}", "720")

                    embed = discord.Embed(
                        title=f"🎬 New clip, check it out!: {title}",
                        description=f"By **{creator}** — [{login} on Twitch]({f'https://twitch.tv/{login}'})",
                        timestamp=created_at,
                    )
                    if thumb:
                        embed.set_image(url=thumb)
                    embed.add_field(name="Watch", value=url, inline=False)
                    embed.set_footer(text=f"{login}")

                    try:
                        await ch.send(embed=embed)
                    except discord.Forbidden:
                        await ch.send(f"🎬 New clip by **{creator}** — {url}")
                    except Exception:
                        pass

                    if created_at > latest_seen:
                        latest_seen = created_at

                self.clip_checkpoint[login] = latest_seen

        except Exception:
            pass

    @check_clips.before_loop
    async def before_check_clips(self):
        await self.bot.wait_until_ready()

    #Manual live test.
    @commands.command(name="livecheck")
    async def livecheck_cmd(self, ctx):
        """Manually checks Twitch live status and announces if needed."""
        try:
            streams = await self._fetch_streams(TWITCH_STREAMER)
            live_now = {s["user_login"].lower(): s for s in streams if s.get("type") == "live"}
            await ctx.send(f"Twitch says LIVE now: {list(live_now.keys()) or 'none'}")

            if not live_now:
                return

            ch = self.bot.get_channel(TWITCH_LIVE) or await self.bot.fetch_channel(TWITCH_LIVE)
            users = await self._fetch_users(list(live_now.keys()))
            posted = []
            for login, stream in live_now.items():
                started_at = stream.get("started_at")
                if started_at and self.last_live_started_at.get(login) == started_at:
                    continue
                user = users.get(login) or {"login": login, "display_name": login, "profile_image_url": None}
                await self._announce(ch, stream, user)
                if started_at:
                    self.last_live_started_at[login] = started_at
                posted.append(login)

            if posted:
                await ctx.send(f"Announced: {', '.join(posted)}")
            else:
                await ctx.send("ℹ Nothing new to announce (already announced this session).")
        except Exception as e:
            await ctx.send(f"Livecheck error :( see: `{e}`")

    #Cleanup.
    async def cog_unload(self):
        self.check_streams.cancel()
        self.check_streams_priority.cancel()
        if hasattr(self, "check_clips"):
            self.check_clips.cancel()
        if self.session:
            await self.session.close()

#Add cog.
async def setup(bot):
    await bot.add_cog(TwitchCog(bot))