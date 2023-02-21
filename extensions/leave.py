from discord.ext import commands
from utils.dpyexcept import excepter
from constant import GUILD_ID

class LeaveCog(commands.Cog):
    """退出時の処理"""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    @excepter
    async def on_member_remove(self, member):
        guild = member.guild
        if guild.id != GUILD_ID:
            return
        await guild.system_channel.send(f'{member.mention} が退出しました')

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(LeaveCog(bot))
