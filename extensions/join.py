from discord.ext import commands
from utils.dpyexcept import excepter
from constant import GUILD_ID
from constant import ROLE_MEMBER_ID
from constant import ROLE_BOT_LIMITED_ID

class JoinCog(commands.Cog):
    """入室時の処理"""
    def __init__(self, bot):
        self.bot = bot

    @commands.Cog.listener()
    @excepter
    async def on_member_join(self, member):
        if member.guild.id != GUILD_ID:
            return
        if member.bot:
            role_bot_limited = member.guild.get_role(ROLE_BOT_LIMITED_ID)
            await member.add_roles(role_bot_limited)
        else:
            role_member = member.guild.get_role(ROLE_MEMBER_ID)
            await member.add_roles(role_member)

async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(JoinCog(bot))
