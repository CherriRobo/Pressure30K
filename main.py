#Imports.
import os
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
import asyncio

#Load env.
load_dotenv()
logging.basicConfig(level = logging.INFO)
SERVER_ID = int(os.getenv("SERVER_ID", 0)) or None
SYNC_SERVER = [discord.Object(id = SERVER_ID)] if SERVER_ID else None

#Intents.
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

#Prefix.
bot = commands.Bot(command_prefix = "!", intents = intents, help_command = None)

#Load bot.
@bot.event
async def on_ready():
    logging.info("Welcome back Dani!")
    try:
        if SYNC_SERVER:
            await bot.tree.sync(guild=SYNC_SERVER[0])
            logging.info("Synced app commands!")
        else:
            await bot.tree.sync()
            logging.info("Synced global app commands!")
    except Exception as e:
        logging.exception("Slash command sync failed :( see: ", e)

    # Twitch check on start-up.
    twitch_cog = bot.get_cog("TwitchCog")
    if twitch_cog:
        await twitch_cog.trigger_now()

    #DND and status.
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.CustomActivity(name="Pressure30k is a gnome (4ft2) who is Bronze ranked in Apex Legends.")
    )

#Load cogs.
async def setup_cogs():
    for ext in ("cogs.welcome","cogs.twitch", "cogs.embed", "cogs.reaction_roles", "cogs.autorole", "cogs.ban_kick"):
        try:
            await bot.load_extension(ext)
            logging.info(f"Loaded {ext}!")
        except Exception:
            logging.exception(f"Failed to load :( see: {ext}")

#Run token.
if __name__ == "__main__":
    asyncio.run(setup_cogs())
    bot.run(os.getenv("TOKEN"))