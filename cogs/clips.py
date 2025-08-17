#Imports.
import os
import discord
from discord.ext import commands, tasks
from datetime import datetime, timedelta, timezone
from typing import Dict, List
from twitch_api import TwitchAPI

#Load env.
TWITCH_STREAMER: List[str] = [s.strip().lower() for s in os.getenv("TWITCH_STREAMER", "").split(",") if s.strip()]
CLIP_CHANNEL: int = int(os.getenv("CLIP_CHANNEL", "0"))
CLIP_POLL: int = int(os.getenv("CLIP_POLL", "300"))
CLIP_WINDOW_MIN: int = int(os.getenv("CLIP_WINDOW_MIN", "60"))

#Cogs.
class ClipsCog(commands.Cog):
    def __init__(self, bot: commands.Bot, api: TwitchAPI):
        self.bot = bot
        self.api = api
        self.clip_checkpoint: Dict[str, datetime] = {}
        self._broadcaster_ids: Dict[str, str] = {}
        if CLIP_CHANNEL and TWITCH_STREAMER:
            self.check_clips.start()

    async def _ensure_broadcaster_ids(self):
        if not self._broadcaster_ids:
            self._broadcaster_ids = await self.api.fetch_broadcaster_ids(TWITCH_STREAMER)

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
                    if url:
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