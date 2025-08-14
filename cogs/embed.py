#Imports.
import discord
from discord.ext import commands

#Cogs.
class EmbedPost(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    #Send an embed to a given channel.
    @commands.command(name="postembed")
    @commands.has_permissions(manage_guild=True)
    async def postembed(self, ctx, channel: discord.TextChannel, title: str, *, description: str):
        """!postembed #channel "Title" "Description"."""
        #Remove quotes.
        if description.startswith('"') and description.endswith('"'):
            description = description[1:-1]

        #Convert \n.
        description = description.replace("\\n", "\n")
        
        embed = discord.Embed(title=title, description=description)
        try:
            await channel.send(embed=embed)
            await ctx.send(f"Embed posted in {channel.mention}", delete_after=5)
        except discord.Forbidden:
            await ctx.send("I don't have permission to post in that channel.", delete_after=5)

#Add cog.
async def setup(bot):
    await bot.add_cog(EmbedPost(bot))