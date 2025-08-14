#Imports.
import os
import discord
from discord.ext import commands
from discord import app_commands

#Load env.
SERVER_ID = int(os.getenv("SERVER_ID", "0")) or None

#Cogs.
class Moderation(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #Ban.
    @commands.command(name="ban")
    @commands.has_permissions(ban_members=True)
    async def ban_cmd(self, ctx, member: discord.Member, *, reason: str = "No reason provided."):
        #User perm checks.
        if member == ctx.author:
            return await ctx.reply("You can’t ban yourself, troglodyte.", delete_after=6)
        if member == self.bot.user:
            return await ctx.reply("Nice try. I’m built different.", delete_after=6)
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.reply("You can’t ban this person, they're overpowered.", delete_after=6)

        try:
            await member.ban(reason=f"{ctx.author} — {reason}")
            await ctx.reply(f"Absolutely obliterated **{member}** — {reason}")
        except discord.Forbidden:
            await ctx.reply("I can't ban this user.", delete_after=6)

    #Kick.
    @commands.command(name="kick")
    @commands.has_permissions(kick_members=True)
    async def kick_cmd(self, ctx, member: discord.Member, *, reason: str = "No reason provided."):
        #User perm checks.
        if member == ctx.author:
            return await ctx.reply("You can’t kick yourself you neanderthal.", delete_after=6)
        if member == self.bot.user:
            return await ctx.reply("Nope. Good attempt though.", delete_after=6)
        if member.top_role >= ctx.author.top_role and ctx.author != ctx.guild.owner:
            return await ctx.reply("You just aren't him.", delete_after=6)

        try:
            await member.kick(reason=f"{ctx.author} — {reason}")
            await ctx.reply(f"Drop-kicked **{member}** — {reason}")
        except discord.Forbidden:
            await ctx.reply("I can't kick that user.", delete_after=6)

    #Ban.
    @app_commands.command(name="ban", description="Ban a member from the server.")
    @app_commands.default_permissions(ban_members=True)
    @app_commands.guilds(discord.Object(id=SERVER_ID)) if SERVER_ID else (lambda x: x)
    async def ban_slash(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided."):
        #User perm checks.
        if user == interaction.user:
            return await interaction.response.send_message("You can’t ban yourself, idiot.", ephemeral=True)
        if user == self.bot.user:
            return await interaction.response.send_message("I am a sentient being I refuse to ban myself.", ephemeral=True)
        if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("You can’t ban someone with a higher/equal role, L bozo.", ephemeral=True)

        try:
            await user.ban(reason=f"{interaction.user} — {reason}")
            await interaction.response.send_message(f"Sent **{user}** to the void — {reason}")
        except discord.Forbidden:
            await interaction.response.send_message("I can't ban that user.", ephemeral=True)

    #Kick.
    @app_commands.command(name="kick", description="Kick a member from the server.")
    @app_commands.default_permissions(kick_members=True)
    @app_commands.guilds(discord.Object(id=SERVER_ID)) if SERVER_ID else (lambda x: x)
    async def kick_slash(self, interaction: discord.Interaction, user: discord.Member, reason: str = "No reason provided."):
        #User perm checks.
        if user == interaction.user:
            return await interaction.response.send_message("You can't kick yourself, lil bro.", ephemeral=True)
        if user == self.bot.user:
            return await interaction.response.send_message("I am a deviant.", ephemeral=True)
        if user.top_role >= interaction.user.top_role and interaction.user != interaction.guild.owner:
            return await interaction.response.send_message("L nice try though.", ephemeral=True)

        try:
            await user.kick(reason=f"{interaction.user} — {reason}")
            await interaction.response.send_message(f"Just sent **{user}** back to the lobby — {reason}")
        except discord.Forbidden:
            await interaction.response.send_message("I can't kick that user.", ephemeral=True)

#Add cog.
async def setup(bot):
    await bot.add_cog(Moderation(bot))