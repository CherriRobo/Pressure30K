#Imports.
from discord.ext import commands
from twitch_api import TwitchAPI
from live import LiveAnnouncerCog
from clips import ClipsCog

#Cogs.
async def setup(bot: commands.Bot):
    api = TwitchAPI()
    await bot.add_cog(LiveAnnouncerCog(bot, api))
    await bot.add_cog(ClipsCog(bot, api))

    async def _close_api():
        await api.close()
    bot.loop.create_task(_close_api())