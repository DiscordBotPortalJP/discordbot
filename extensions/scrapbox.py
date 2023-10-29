import discord
import urllib.parse
from discord import app_commands
from discord.ext import commands
from utils.dpyexcept import excepter

SCRAPBOX_PROJECT_NAME = 'discordbotjp'


async def create_scrapbox_page(title: str, content: str):
    url = f'https://scrapbox.io/{SCRAPBOX_PROJECT_NAME}/{title}'
    encoded_body = urllib.parse.quote(content)
    return f'{url}?body={encoded_body}'


class CreateScrapboxPageModal(discord.ui.Modal, title='Scrapboxにページを作成する'):
    def __init__(self):
        super().__init__()

    page_title = discord.ui.TextInput(
        style=discord.TextStyle.short,
        label='ページタイトル',
        required=True,
    )
    lines = discord.ui.TextInput(
        style=discord.TextStyle.long,
        label='ページ内容',
        required=True,
    )

    @excepter
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        url = await create_scrapbox_page(self.page_title.value, self.lines.value)
        await interaction.followup.send(f'このURLにアクセスするとページの作成が完了します。\n{url}', ephemeral=True)        

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.followup.send('エラーが発生しました', ephemeral=True)


class ReprintScrapboxPageModal(discord.ui.Modal, title='Scrapboxに投稿を転載する'):
    def __init__(self, content: str):
        super().__init__()
        self.content = content

    page_title = discord.ui.TextInput(
        style=discord.TextStyle.short,
        label='ページタイトル',
        required=True,
    )

    @excepter
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        url = await create_scrapbox_page(self.page_title.value, self.content)
        await interaction.followup.send(f'このURLにアクセスするとページの作成が完了します。\n{url}', ephemeral=True)        

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.followup.send('エラーが発生しました', ephemeral=True)


class ScrapboxCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name='Scrapboxに転載する',
            callback=self._reprint_scrapbox_context_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)

    @app_commands.command(name='scrapboxにページを作成する')
    @app_commands.guild_only()
    @excepter
    async def _create_scrapbox_page(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateScrapboxPageModal())

    @app_commands.guild_only()
    @excepter
    async def _reprint_scrapbox_context_menu(self, interaction: discord.Interaction, message: discord.Message):
        await interaction.response.send_modal(ReprintScrapboxPageModal(message.content))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ScrapboxCog(bot))
