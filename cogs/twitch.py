#Imports.
import os
import time
import asyncio
import aiohttp
import discord
from discord.ext import commands, tasks
from discord import app_commands
from datetime import datetime, timedelta, timezone
import logging

#Load env.
TWITCH_CLIENT = os.getenv("TWITCH_CLIENT")
TWITCH_SECRET = os.getenv("TWITCH_SECRET")
TWITCH_STREAMER = [s.strip().lower() for s in os.getenv("TWITCH_STREAMER", "").split(",") if s.strip()]
TWITCH_LIVE = int(os.getenv("TWITCH_LIVE", "0"))
TWITCH_POLL = int(os.getenv("TWITCH_POLL", "120"))
SERVER_ID = int(os.getenv("SERVER_ID", "0")) or None
CLIP_CHANNEL = int(os.getenv("CLIP_CHANNEL", "0"))
CLIP_POLL = int(os.getenv("CLIP_POLL", "300"))
CLIP_WINDOW_MIN = int(os.getenv("CLIP_WINDOW_MIN", "60"))

#Helix.
HELIX = "https://api.twitch.tv/helix"

#Logger.
log = logging.getLogger("twitch_cog")

#Cogs.
class TwitchCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.session: aiohttp.ClientSession | None = None
        self.token: str | None = None
        self.token_expiry_ts: float = 0.0
        self.live_cache: set[str] = set()
        self.clip_checkpoint: dict[str, datetime] = {}
        log.info("TwitchCog init. CLIP_CHANNEL=%s STREAMERS=%s", CLIP_CHANNEL, TWITCH_STREAMER)
        self.check_streams.start()
        if CLIP_CHANNEL and TWITCH_STREAMER:
            self.check_clips.start()

    #Check Live on start-up.
    async def trigger_now(self):
        await self._check_streams_once()

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
                if login not in self.live_cache:
                    user = users.get(login)
                    if user:
                        await self._announce(channel, stream, user)
            self.live_cache = set(live_now.keys())
        except Exception:
            pass

    #Stop loop, close HTTP.
    async def cog_unload(self):
        self.check_streams.cancel()
        if hasattr(self, "check_clips"):
            self.check_clips.cancel()
        if self.session:
            await self.session.close()

    #Aiohttp session.
    async def _get_session(self) -> aiohttp.ClientSession:
        if self.session and not self.session.closed:
            return self.session
        self.session = aiohttp.ClientSession()
        return self.session

    #Twitch API token.
    async def _ensure_token(self):
        if self.token and time.time() < self.token_expiry_ts - 60:
            return
        sess = await self._get_session()
        async with sess.post(
            "https://id.twitch.tv/oauth2/token",
            data={
                "client_id": TWITCH_CLIENT,
                "client_secret": TWITCH_SECRET,
                "grant_type": "client_credentials",
            },
            timeout=20
        ) as r:
            data = await r.json()
            self.token = data.get("access_token")
            expires_in = int(data.get("expires_in", 3600))
            self.token_expiry_ts = time.time() + expires_in
            log.info("Twitch token refreshed (expires_in=%ss)", expires_in)

    #Return the headers.
    async def _helix_headers(self):
        await self._ensure_token()
        return {
            "Client-ID": TWITCH_CLIENT,
            "Authorization": f"Bearer {self.token}",
        }

    #Fetch stream data.
    async def _fetch_streams(self, logins: list[str]):
        if not logins:
            return []
        sess = await self._get_session()
        params = [("user_login", u) for u in logins]
        async with sess.get(f"{HELIX}/streams", params=params, headers=await self._helix_headers(), timeout=20) as r:
            data = await r.json()
            return data.get("data", [])

    #Fetch user data.
    async def _fetch_users(self, logins: list[str]):
        if not logins:
            return {}
        sess = await self._get_session()
        params = [("login", u) for u in logins]
        async with sess.get(f"{HELIX}/users", params=params, headers=await self._helix_headers(), timeout=20) as r:
            data = await r.json()
            return {u["login"].lower(): u for u in data.get("data", [])}

    #Fetch user data.
    async def _fetch_broadcaster_ids(self, logins: list[str]) -> dict[str, str]:
        users = await self._fetch_users(logins)
        return {login: u.get("id") for login, u in users.items() if u.get("id")}

    #Fetch clips since a timestamp.
    async def _fetch_clips(self, broadcaster_id: str, started_at_iso: str):
        sess = await self._get_session()
        params = {
            "broadcaster_id": broadcaster_id,
            "started_at": started_at_iso,
            "first": 20,
        }
        async with sess.get(f"{HELIX}/clips", params=params, headers=await self._helix_headers(), timeout=20) as r:
            data = await r.json()
            return data.get("data", []) or []

    #Twitch thumbnail.
    def _stream_thumb(self, streamer_login: str) -> str:
        return f"https://static-cdn.jtvnw.net/previews-ttv/live_user_{streamer_login}-1280x720.jpg"

    #Live announcement.
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
            allowed_mentions=discord.AllowedMentions(roles=True)
        )

    #Live poll.
    @tasks.loop(seconds=TWITCH_POLL)
    async def check_streams(self):
        await self.bot.wait_until_ready()
        await self._check_streams_once()

    #Bot ready before loop.
    @check_streams.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    #Clip poll.
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
                since = self.clip_checkpoint.get(login)
                if since is None:
                    since = now - timedelta(minutes=CLIP_WINDOW_MIN)
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
                        timestamp=created_at
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

    #Ensure bot ready before clips loop.
    @check_clips.before_loop
    async def before_check_clips(self):
        await self.bot.wait_until_ready()

#Add cog.
async def setup(bot):
    await bot.add_cog(TwitchCog(bot))