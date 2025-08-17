#Imports.
import os
import logging
from dotenv import load_dotenv
import discord
from discord.ext import commands
from discord import app_commands
import asyncio
import logging
logging.basicConfig(level=logging.INFO)

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

    #DND and status.
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.CustomActivity(name="Watching over the server.")
    )

#Load cogs.
async def setup_cogs():
    for ext in ("cogs.cog_setup", "cogs.welcome","cogs.twitch_api", "cogs.embed", "cogs.reaction_roles", "cogs.autorole", "cogs.ban_kick", "cogs.live", "cogs.clips", ""):
        try:
            await bot.load_extension(ext)
            logging.info(f"Loaded {ext}!")
        except Exception:
            logging.exception(f"Failed to load :( see: {ext}")

#Run token.
if __name__ == "__main__":
    asyncio.run(setup_cogs())
    bot.run(os.getenv("TOKEN"))