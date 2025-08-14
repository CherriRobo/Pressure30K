#Imports.
import os
import discord
from discord.ext import commands
from discord import app_commands

#Load env.
WELCOME = int(os.getenv("WELCOME_CHANNEL", "0"))
DEFAULT_ROLE = int(os.getenv("DEFAULT_ROLE", "0"))
SERVER_ID = int(os.getenv("SERVER_ID", "0")) or None

#Cogs.
class Welcome(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        if DEFAULT_ROLE:
            role = member.guild.get_role(DEFAULT_ROLE)
            if role:
                try:
                    await member.add_roles(role, reason="Auto-assign")
                except discord.Forbidden:
                    pass
        
        if WELCOME:
            channel = member.guild.get_channel(WELCOME)
            if channel and isinstance(channel, (discord.TextChannel, discord.Thread)):
                embed = discord.Embed(title = "Welcome!", description = f"Hey {member.mention}, welcome to **{member.guild.name}!**")
                embed.set_thumbnail(url = member.display_avatar.url)
                await channel.send(embed = embed)

#Add cog.
async def setup(bot):
    await bot.add_cog(Welcome(bot))