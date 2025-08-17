#Imports.
import os
import logging
import asyncio
from dotenv import load_dotenv
import discord
from discord.ext import commands

#Loging.
logging.basicConfig(level=logging.INFO)

#Load env.
load_dotenv()
SERVER_ID = int(os.getenv("SERVER_ID", 0)) or None
SYNC_SERVER = [discord.Object(id=SERVER_ID)] if SERVER_ID else None
TOKEN = os.getenv("TOKEN")

#Intents.
intents = discord.Intents.default()
intents.members = True
intents.message_content = True

#Prefix.
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

#Load cogs.
EXTENSIONS = [
    "cogs.welcome",
    "cogs.embed",
    "cogs.reaction_roles",
    "cogs.autorole",
    "cogs.ban_kick",
    "cogs.live",
    "cogs.clips",
]

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
        logging.exception("Slash command sync failed :( see: %s", e)

    # DND and status.
    await bot.change_presence(
        status=discord.Status.dnd,
        activity=discord.CustomActivity(name="Watching over the server.")
    )

#Cog loader.
async def load_extensions():
    for ext in EXTENSIONS:
        try:
            await bot.load_extension(ext)
            logging.info(f"Loaded {ext}!")
        except Exception:
            logging.exception(f"Failed to load :( see: {ext}")

#TwitchAPI.
async def main():
    from cogs.twitch_api import TwitchAPI
    api = TwitchAPI()
    bot.twitch_api = api

    try:
        await load_extensions()
        await bot.start(TOKEN)
    finally:
        try:
            await api.close()
        except Exception:
            logging.exception("Error while closing TwitchAPI")

#Run token.
if __name__ == "__main__":
    asyncio.run(main())