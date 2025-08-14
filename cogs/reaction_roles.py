#Imports.
import os
import discord
from discord.ext import commands

#Load env.
ROLE_PURPLE = int(os.getenv("ROLE_PURPLE", 0))
ROLE_BLUE = int(os.getenv("ROLE_BLUE", 0))
ROLE_MSG_ID = int(os.getenv("ROLE_MSG_ID", 0))
ROLE_CHANNEL_ID = int(os.getenv("ROLE_CHANNEL_ID", 0))

ROLE_TWITCH = int(os.getenv("ROLE_TWITCH", 0))
ROLE_SERVER = int(os.getenv("ROLE_SERVER", 0))
NOTIF_MSG = int(os.getenv("NOTIF_MSG", 0))

MEMBER = int(os.getenv("MEMBER", 0))

#Cogs.
class ReactionRoles(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.color_emoji_to_role = {
            "🟣": ROLE_PURPLE,
            "🔵": ROLE_BLUE,
        }
        self.notif_emoji_to_role = {
            "🔴": ROLE_TWITCH,
            "📌": ROLE_SERVER,
        }

    @commands.Cog.listener()
    async def on_ready(self):
        #Add and remove reactions. Colours.
        channel = self.bot.get_channel(ROLE_CHANNEL_ID)
        if isinstance(channel, discord.TextChannel) and ROLE_MSG_ID:
            try:
                message = await channel.fetch_message(ROLE_MSG_ID)
                for emoji in self.color_emoji_to_role.keys():
                    if not any(str(r.emoji) == emoji for r in message.reactions):
                        await message.add_reaction(emoji)
                for reaction in message.reactions:
                    if str(reaction.emoji) not in self.color_emoji_to_role:
                        async for user in reaction.users():
                            await message.remove_reaction(reaction.emoji, user)
            except discord.NotFound:
                print(f"Message with ID {ROLE_MSG_ID} not found in channel {ROLE_CHANNEL_ID}.")
            except discord.Forbidden:
                print("Bot doesn't have permission to add/remove reactions.")
            except discord.HTTPException as e:
                print(f"HTTP error while managing reactions: {e}")

        #Notifs message.
        if NOTIF_MSG:
            for g in self.bot.guilds:
                for ch in g.text_channels:
                    try:
                        msg = await ch.fetch_message(NOTIF_MSG)
                    except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                        continue
                    else:
                        for emoji in self.notif_emoji_to_role.keys():
                            if not any(str(r.emoji) == emoji for r in msg.reactions):
                                await msg.add_reaction(emoji)
                        for reaction in msg.reactions:
                            if str(reaction.emoji) not in self.notif_emoji_to_role:
                                async for user in reaction.users():
                                    await msg.remove_reaction(reaction.emoji, user)
                        break

    @commands.Cog.listener()
    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        #Ignore bot's own reactions.
        if payload.user_id == self.bot.user.id:
            return

        if payload.message_id == ROLE_MSG_ID and ROLE_MSG_ID:
            await self._handle_reaction_add(payload, self.color_emoji_to_role)
            return

        if payload.message_id == NOTIF_MSG and NOTIF_MSG:
            await self._handle_reaction_add(payload, self.notif_emoji_to_role)
            return

    @commands.Cog.listener()
    async def on_raw_reaction_remove(self, payload: discord.RawReactionActionEvent):
        if payload.message_id == ROLE_MSG_ID and ROLE_MSG_ID:
            await self._handle_reaction_remove(payload, self.color_emoji_to_role)
            return

        if payload.message_id == NOTIF_MSG and NOTIF_MSG:
            await self._handle_reaction_remove(payload, self.notif_emoji_to_role)
            return

    async def _handle_reaction_add(self, payload: discord.RawReactionActionEvent, mapping: dict[str, int]):
        #Remove any other emoji.
        if str(payload.emoji) not in mapping:
            channel = self.bot.get_channel(payload.channel_id)
            if isinstance(channel, discord.TextChannel):
                try:
                    message = await channel.fetch_message(payload.message_id)
                    user = payload.member or (await self.bot.fetch_user(payload.user_id))
                    await message.remove_reaction(payload.emoji, user)
                except Exception:
                    pass
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        role_id = mapping.get(str(payload.emoji))
        if not role_id:
            return
        role = guild.get_role(role_id)
        if role is None:
            return

        member = payload.member or guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except Exception:
                return

        try:
            await member.add_roles(role, reason="Reaction role add")
        except discord.Forbidden:
            pass

    async def _handle_reaction_remove(self, payload: discord.RawReactionActionEvent, mapping: dict[str, int]):
        if str(payload.emoji) not in mapping:
            return

        guild = self.bot.get_guild(payload.guild_id)
        if guild is None:
            return

        role_id = mapping.get(str(payload.emoji))
        if not role_id:
            return
        role = guild.get_role(role_id)
        if role is None:
            return

        member = guild.get_member(payload.user_id)
        if member is None:
            try:
                member = await guild.fetch_member(payload.user_id)
            except Exception:
                return

        try:
            await member.remove_roles(role, reason="Reaction role remove")
        except discord.Forbidden:
            pass

#Add cog.
async def setup(bot):
    await bot.add_cog(ReactionRoles(bot))