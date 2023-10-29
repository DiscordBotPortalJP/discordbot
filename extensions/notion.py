import aiohttp
import discord
import datetime
from discord import app_commands
from discord.ext import commands
from utils.dpyexcept import excepter
from constant import NOTION_API_KEY
from constant import NOTION_DATABASE_ID

url = 'https://api.notion.com/v1/pages'

headers =  {
    'Notion-Version': '2022-06-28',
    'Authorization': f'Bearer {NOTION_API_KEY}',
    'Content-Type': 'application/json',
}


def compose_payload(title: str, content: str, user: discord.Member, wrote_at: datetime.datetime, tags : list[str] = None, message_url: str = None):
    properties = {
        'title': { 'title': [ { 'text': { 'content': title } } ] },
        'user_id': { 'number':  user.id },
        'wrote_at': { 'date': { 'start': wrote_at.isoformat() } },
        # 'user_name': { 'rich_text': [ { 'text': { 'content': user.name } } ] },
    }
    if tags:
        properties['tag'] = { 'multi_select': [{'name': tag} for tag in tags] }
    if message_url:
        properties['message_url'] = { 'url': message_url }
    return {
        'parent': {
            'database_id': NOTION_DATABASE_ID,
        },
        'properties': properties,
        'children': [
            {
                'object': 'block',
                'type': 'paragraph',
                'paragraph': {
                    'rich_text': [
                        {
                            'type': 'text',
                            'text': {'content': content },
                        }
                    ]
                }
            }
        ],
    }


async def create_notion_page(title: str, content: str, user: discord.Member, wrote_at: datetime.datetime, tags: list[str] = None, message_url: str = None):
    payload = compose_payload(title, content, user, wrote_at, tags, message_url)
    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=payload) as response:
            result = await response.json()
            if response.status == 200:
                page_url = result.get('url')
                return page_url
            else:
                print(f'Failed to create page in Notion. Status code: {response.status}')
                print(result)
                return None


class CreateNotionPageModal(discord.ui.Modal, title='Notionにページを作成する'):
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
    tags = discord.ui.TextInput(
        style=discord.TextStyle.long,
        label='タグ（1行ごとに1タグ）',
        required=False,
    )

    @excepter
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        now = datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=9)))
        tags = self.tags.value.splitlines() if self.tags.value else None
        url = await create_notion_page(self.page_title.value, self.lines.value, interaction.user, now, tags)
        if url is None:
            await interaction.followup.send(
                'エラーが発生しました',
                embed=discord.Embed(
                    title=self.page_title.value,
                    description=self.lines.value,
                ),
                ephemeral=True,
            )
            return
        await interaction.followup.send(f'Notionにページを作成しました。\n{url}', ephemeral=True)        

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.followup.send('エラーが発生しました', ephemeral=True)


class ReprintNotionPageModal(discord.ui.Modal, title='Notionに投稿を転載する'):
    def __init__(self, message: discord.Message):
        super().__init__()
        self.message = message

    page_title = discord.ui.TextInput(
        style=discord.TextStyle.short,
        label='ページタイトル',
        required=True,
    )
    tags = discord.ui.TextInput(
        style=discord.TextStyle.long,
        label='タグ（1行ごとに1タグ）',
        required=False,
    )

    @excepter
    async def on_submit(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        tags = self.tags.value.splitlines() if self.tags.value else None
        url = await create_notion_page(self.page_title.value, self.message.content, self.message.author, self.message.created_at, tags, self.message.jump_url)
        if url is None:
            await interaction.followup.send(
                'エラーが発生しました',
                embed=discord.Embed(
                    title=self.page_title.value,
                    description=self.message.content,
                ),
                ephemeral=True,
            )
            return
        await interaction.followup.send(f'Notionにページを作成しました。\n{url}', ephemeral=True)        

    async def on_error(self, interaction: discord.Interaction, error: Exception) -> None:
        await interaction.followup.send('エラーが発生しました', ephemeral=True)


class NotionCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.ctx_menu = app_commands.ContextMenu(
            name='Notionに転載する',
            callback=self._reprint_notion_context_menu,
        )
        self.bot.tree.add_command(self.ctx_menu)

    @app_commands.command(name='notionにページを作成する')
    @app_commands.guild_only()
    @excepter
    async def _create_notion_page(self, interaction: discord.Interaction):
        await interaction.response.send_modal(CreateNotionPageModal())

    @app_commands.guild_only()
    @excepter
    async def _reprint_notion_context_menu(self, interaction: discord.Interaction, message: discord.Message):
        await interaction.response.send_modal(ReprintNotionPageModal(message))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(NotionCog(bot))
