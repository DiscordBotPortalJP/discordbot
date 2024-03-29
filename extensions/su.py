import asyncio
import discord
from discord import app_commands
from discord.ext import commands
from utils.dpyexcept import excepter
from constant import GUILD_ID
from constant import ROLE_STAFF_ID
from constant import ROLE_STAFF_PERMISSION_ID
from constant import ROLE_COMMITTER_ID
from constant import ROLE_COMMITTER_PERMISSION_ID

EXPIRATION_MINUTES = 600  # 解除までの時間

def is_staff(author) -> bool:
    return ROLE_STAFF_ID in [role.id for role in author.roles]

def is_committer(author) -> bool:
    return ROLE_COMMITTER_ID in [role.id for role in author.roles]

class SuCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name='su', description='運営/Committer権限を一時的に付与します')
    @app_commands.guilds(GUILD_ID)
    @app_commands.guild_only()
    @excepter
    async def authorization(self, interaction: discord.Interaction):
        permission_role = None
        if is_staff(interaction.user):
            permission_role = interaction.guild.get_role(ROLE_STAFF_PERMISSION_ID)
        elif is_committer(interaction.user):
            permission_role = interaction.guild.get_role(ROLE_COMMITTER_PERMISSION_ID)
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


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SuCog(bot))
