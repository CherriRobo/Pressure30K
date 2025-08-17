#Imports.
import os
import json
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Set

#Load env.
TWITCH_STREAMER: List[str] = [s.strip().lower() for s in os.getenv("TWITCH_STREAMER", "").split(",") if s.strip()]
CLIP_CHANNEL: int = int(os.getenv("CLIP_CHANNEL", "0"))
CLIP_POLL: int = int(os.getenv("CLIP_POLL", "300"))
CLIP_WINDOW_MIN: int = int(os.getenv("CLIP_WINDOW_MIN", "60"))
BACKLOG_FILE: str = "backlog_clips.json"

#Cogs.
class ClipsCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api = bot.twitch_api
        self.clip_checkpoint: Dict[str, datetime] = {}
        self._broadcaster_ids: Dict[str, str] = {}
        self.seen: Dict[str, Set[str]] = {}

        self._load_backlog()

        if CLIP_CHANNEL and TWITCH_STREAMER:
            self.check_clips.start()

    #Backlog load/save.
    def _load_backlog(self):
        try:
            if os.path.exists(BACKLOG_FILE):
                with open(BACKLOG_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.seen = {k.lower(): set(v) for k, v in data.get("seen", {}).items()}
            else:
                self.seen = {}
        except Exception:
            self.seen = {}

    def _save_backlog(self):
        try:
            payload = {"seen": {k: sorted(list(v)) for k, v in self.seen.items()}}
            with open(BACKLOG_FILE, "w", encoding="utf-8") as f:
                json.dump(payload, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    #Helpers.
    async def _ensure_broadcaster_ids(self):
        if not self._broadcaster_ids:
            self._broadcaster_ids = await self.api.fetch_broadcaster_ids(TWITCH_STREAMER)

    def _is_seen(self, login: str, clip_id: str) -> bool:
        return clip_id in self.seen.get(login.lower(), set())

    def _mark_seen(self, login: str, clip_id: str):
        login = login.lower()
        if login not in self.seen:
            self.seen[login] = set()
        self.seen[login].add(clip_id)

    #Tasks.
    @tasks.loop(seconds=CLIP_POLL)
    async def check_clips(self):
        await self.bot.wait_until_ready()
        if not (CLIP_CHANNEL and TWITCH_STREAMER):
            return

        ch = self.bot.get_channel(CLIP_CHANNEL) or await self.bot.fetch_channel(CLIP_CHANNEL)
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
            await self._ensure_broadcaster_ids()
            now = datetime.now(timezone.utc)

            for login, bid in self._broadcaster_ids.items():
                since = self.clip_checkpoint.get(login) or (now - timedelta(minutes=CLIP_WINDOW_MIN))
                started_at_iso = since.isoformat().replace("+00:00", "Z")
                clips = await self.api.fetch_clips(bid, started_at_iso)

                def parse_ts(c):
                    try:
                        return datetime.fromisoformat(c["created_at"].replace("Z", "+00:00"))
                    except Exception:
                        return since

                clips.sort(key=parse_ts)
                latest_seen = since
                posted = False

                for clip in clips:
                    clip_id = clip.get("id")
                    if not clip_id:
                        continue
                    if self._is_seen(login, clip_id):
                        ts = parse_ts(clip)
                        if ts > latest_seen:
                            latest_seen = ts
                        continue

                    created_at = parse_ts(clip)
                    if created_at <= since:
                        if created_at > latest_seen:
                            latest_seen = created_at
                        continue

                    url = clip.get("url")
                    title = clip.get("title") or "New clip"
                    creator = clip.get("creator_name") or "Someone"
                    thumb = clip.get("thumbnail_url")
                    if thumb and "{width}" in thumb:
                        thumb = thumb.replace("{width}", "1280").replace("{height}", "720")

                    embed = discord.Embed(
                        title=f"🎬 New clip: {title}",
                        description=f"By **{creator}** — [{login} on Twitch]({f'https://twitch.tv/{login}'})",
                        timestamp=created_at,
                    )
                    if thumb:
                        embed.set_image(url=thumb)
                    if url:
                        embed.add_field(name="Watch", value=url, inline=False)
                    embed.set_footer(text=f"{login}")

                    try:
                        await ch.send(embed=embed)
                    except discord.Forbidden:
                        if url:
                            await ch.send(f"🎬 New clip by **{creator}** — {url}")
                        else:
                            await ch.send(f"🎬 New clip by **{creator}**")
                    except Exception:
                        continue

                    self._mark_seen(login, clip_id)
                    posted = True
                    if created_at > latest_seen:
                        latest_seen = created_at

                self.clip_checkpoint[login] = latest_seen
                if posted:
                    self._save_backlog()
        except Exception:
            pass

    @check_clips.before_loop
    async def before_check_clips(self):
        await self.bot.wait_until_ready()

async def setup(bot: commands.Bot):
    await bot.add_cog(ClipsCog(bot))