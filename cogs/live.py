# Imports.
import os
import discord
from discord.ext import commands, tasks
from typing import Dict, List, Set

#Load env.
TWITCH_STREAMER: List[str] = [s.strip().lower() for s in os.getenv("TWITCH_STREAMER", "").split(",") if s.strip()]
TWITCH_LIVE: int = int(os.getenv("TWITCH_LIVE", "0"))
TWITCH_POLL: int = int(os.getenv("TWITCH_POLL", "120"))

#Cogs.
class LiveAnnouncerCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.api = bot.twitch_api
        self.last_live_started_at: Dict[str, str] = {}
        self.live_cache: Set[str] = set()
        self.check_streams.start()

    async def _announce(self, channel, stream, user):
        login = user["login"].lower()
        title = stream.get("title") or "Live on Twitch!"
        game = stream.get("game_name") or "Just Chatting"
        url = f"https://twitch.tv/{login}"

        embed = discord.Embed(
            title=f"{user.get('display_name')} is now LIVE!",
            description=f"**{title}**\nPlaying: {game}\n{url}",
        )
        if user.get("profile_image_url"):
            embed.set_thumbnail(url=user.get("profile_image_url"))

        await channel.send(
            content=f"🔴 **{user.get('display_name')}** is live! Come join in and chat! <@&1405373110143684618>",
            embed=embed,
            allowed_mentions=discord.AllowedMentions(roles=True),
        )

    async def _check_streams_once(self):
        if not (TWITCH_STREAMER and TWITCH_LIVE):
            return
        channel = self.bot.get_channel(TWITCH_LIVE) or await self.bot.fetch_channel(TWITCH_LIVE)
        if not hasattr(channel, "send"):
            return

        streams = await self.api.fetch_streams(TWITCH_STREAMER)
        live_now = {s["user_login"].lower(): s for s in streams if s.get("type") == "live"}
        users = await self.api.fetch_users(list(live_now.keys()))

        for login, stream in live_now.items():
            started_at = stream.get("started_at")
            if started_at and self.last_live_started_at.get(login) == started_at:
                continue

            user = users.get(login) or {"login": login, "display_name": login, "profile_image_url": None}
            await self._announce(channel, stream, user)

            if started_at:
                self.last_live_started_at[login] = started_at

        self.live_cache = set(live_now.keys())

    #Tasks.
    @tasks.loop(seconds=TWITCH_POLL)
    async def check_streams(self):
        await self.bot.wait_until_ready()
        try:
            await self._check_streams_once()
        except Exception:
            pass

    @check_streams.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

    #Manual live.
    @commands.command(name="livecheck")
    async def livecheck_cmd(self, ctx: commands.Context):
        try:
            streams = await self.api.fetch_streams(TWITCH_STREAMER)
            live_now = {s["user_login"].lower(): s for s in streams if s.get("type") == "live"}
            await ctx.send(f"Twitch says LIVE now: {list(live_now.keys()) or 'none'}")

            if not live_now:
                return

            ch = self.bot.get_channel(TWITCH_LIVE) or await self.bot.fetch_channel(TWITCH_LIVE)
            users = await self.api.fetch_users(list(live_now.keys()))
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

async def setup(bot: commands.Bot):
    await bot.add_cog(LiveAnnouncerCog(bot))