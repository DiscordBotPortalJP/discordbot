import discord
from discord.ext import commands
from utils.dpyexcept import excepter
from constant import GUILD_ID


class AutoReactionCog(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.emojis_cache = None

    async def fetch_emojis(self) -> list[str]:
        if self.emojis_cache is not None:
            return self.emojis_cache
        guild = self.bot.get_guild(GUILD_ID)
        emoji_ids = (
            '707397881493192757', #increment
            '707397881824411648', #decrement
        )
        self.emojis_cache = [str(await guild.fetch_emoji(emoji_id)) for emoji_id in emoji_ids]
        return self.emojis_cache

    @commands.Cog.listener()
    @excepter
    async def on_message(self, message: discord.Message):
        if message.author.bot:
            if message.channel.id != 645663048778121226: #新着記事
                return
        # BOT制作情報共有, BOT制作質問
        if message.channel.category.id not in [843437704842706974, 828467376218570772]:
            return
        emojis = await self.fetch_emojis()
        for emoji in emojis:
            await message.add_reaction(emoji)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(AutoReactionCog(bot))
