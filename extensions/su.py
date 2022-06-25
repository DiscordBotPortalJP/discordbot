import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from utils.dpyexcept import excepter
from constant import GUILD_ID

EXPIRATION_MINUTES = 600  # 解除までの時間
COMMITTER_ROLE_ID = 704548043537645621
COMMITTER_PERMISSION_ROLE_ID = 858642308642897921
STAFF_ROLE_ID = 741325667550887946
STAFF_PERMISSION_ROLE_ID = 834963970615934996

GUILD = discord.Object(id=GUILD_ID)


def is_committer(author) -> bool:
    return COMMITTER_ROLE_ID in [role.id for role in author.roles]


def is_staff(author) -> bool:
    return STAFF_ROLE_ID in [role.id for role in author.roles]


class SuCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='test')
    @app_commands.guilds(GUILD)
    async def test(self, interaction: discord.Interaction):
        """スラッシュコマンドのテスト"""
        await interaction.response.send_message('スラッシュコマンドのテストだよ！', ephemeral=False)

    @app_commands.command(name='su')
    @app_commands.guilds(GUILD)
    @excepter
    async def authorization(self, interaction: discord.Interaction):
        """運営/Committer権限を一時的に付与します"""
        permission_role = None
        if self.is_staff(interaction.author):
            permission_role = interaction.guild.get_role(STAFF_PERMISSION_ROLE_ID)
        elif self.is_committer(interaction.author):
            permission_role = interaction.guild.get_role(COMMITTER_PERMISSION_ROLE_ID)
        if permission_role is None:
            await interaction.response.send_message(
                '付与できる権限がありません',
                ephemeral=True,
            )
            return

        await interaction.user.add_roles(permission_role)
        await interaction.response.send_message(
            f'{permission_role.name} を付与しました。{EXPIRATION_MINUTES}秒後に解除されます。',
            ephemeral=True,
        )
        await asyncio.sleep(EXPIRATION_MINUTES)
        await interaction.user.remove_roles(permission_role)


async def setup(bot):
    await bot.add_cog(SuCog(bot))
    await bot.tree.sync(guild=GUILD)
