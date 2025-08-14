#Imports.
import os
import discord
from discord.ext import commands

#Load env.
MEMBER = int(os.getenv("MEMBER", 0))

#Cogs.
class AutoRole(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        #Auto-assign member role.
        if MEMBER:
            role = member.guild.get_role(MEMBER)
            if role:
                try:
                    await member.add_roles(role, reason="Auto-assign member role")
                except discord.Forbidden:
                    pass

#Add cog.
async def setup(bot):
    await bot.add_cog(AutoRole(bot))