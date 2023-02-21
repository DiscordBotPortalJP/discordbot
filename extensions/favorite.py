import discord
from discord.ext import commands
from utils import compose_embed_from_message
from utils.dpyexcept import excepter
from constant import GUILD_ID
from constant import CHANNEL_TIPS_ID

class FavoriteCog(commands.Cog):
    """お気に入り機能"""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    @excepter
    async def on_raw_reaction_add(self, payload):
        if payload.guild_id != GUILD_ID:
            return
        if payload.emoji.name != '⭐':
            return
        channel = self.bot.get_channel(payload.channel_id)
        if not isinstance(channel, discord.channel.TextChannel):
            return
        author = channel.guild.get_member(payload.user_id)
        if author.bot:
            return
        message = await channel.fetch_message(payload.message_id)
        await self.bot.get_channel(CHANNEL_TIPS_ID).send(embed=compose_embed_from_message(message))

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(FavoriteCog(bot))
