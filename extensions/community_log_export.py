import datetime
import hashlib
import io
import json
import re
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from constant import LOG_EXPORT_DEFAULT_DAYS
from constant import LOG_EXPORT_GUILD_IDS
from constant import LOG_EXPORT_MAX_MESSAGES
from constant import LOG_EXPORT_OPERATOR_ROLE_IDS
from utils.dpyexcept import excepter


TOKEN_PATTERNS = (
    re.compile(r'mfa\.[A-Za-z0-9_-]{20,}'),
    re.compile(r'[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}'),
)
EMAIL_PATTERN = re.compile(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', re.IGNORECASE)
DISCORD_INVITE_PATTERN = re.compile(r'https?://(?:discord\.gg|discord\.com/invite)/\S+', re.IGNORECASE)
URL_PATTERN = re.compile(r'https?://\S+', re.IGNORECASE)


def has_export_permission(member: discord.Member) -> bool:
    if member.guild.owner_id == member.id:
        return True
    role_ids = {role.id for role in member.roles}
    return any(role_id in role_ids for role_id in LOG_EXPORT_OPERATOR_ROLE_IDS)


def redact_url(match: re.Match) -> str:
    raw_url = match.group(0)
    try:
        host = raw_url.split('/')[2]
    except IndexError:
        host = 'external'
    return f'[link:{host}]'


def sanitize_content(message: discord.Message) -> str:
    content = message.clean_content or message.content or ''
    for pattern in TOKEN_PATTERNS:
        content = pattern.sub('[redacted-token]', content)
    content = EMAIL_PATTERN.sub('[redacted-email]', content)
    content = DISCORD_INVITE_PATTERN.sub('[redacted-discord-invite]', content)
    content = URL_PATTERN.sub(redact_url, content)
    content = re.sub(r'\s+', ' ', content).strip()
    if len(content) > 1800:
        return f'{content[:1800]}...'
    return content


def author_hash(message: discord.Message) -> str:
    seed = f'{message.guild.id}:{message.author.id}'.encode('utf-8')
    return hashlib.sha256(seed).hexdigest()[:16]


def serialize_message(message: discord.Message) -> dict:
    return {
        'id': str(message.id),
        'created_at': message.created_at.astimezone(datetime.timezone.utc).isoformat(),
        'guild_id': str(message.guild.id),
        'guild_name': message.guild.name,
        'channel_id': str(message.channel.id),
        'channel_name': message.channel.name,
        'author_kind': 'bot' if message.author.bot else 'member',
        'author_hash': author_hash(message),
        'content': sanitize_content(message),
        'attachments_count': len(message.attachments),
        'embeds_count': len(message.embeds),
        'jump_url': message.jump_url,
    }


class CommunityLogExportCog(commands.Cog):
    """記事化レビュー用のDiscordログエクスポート機能"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name='ログ記事化エクスポート', description='記事化レビュー用にチャンネルログを匿名化JSONで出力します')
    @app_commands.guild_only()
    @excepter
    async def export_logs_for_articles(
        self,
        interaction: discord.Interaction,
        channel: Optional[discord.TextChannel] = None,
        limit: Optional[int] = None,
        days: Optional[int] = None,
    ):
        guild = interaction.guild
        if guild is None or guild.id not in LOG_EXPORT_GUILD_IDS:
            await interaction.response.send_message('このサーバーではログ記事化エクスポートを利用できません。', ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not has_export_permission(interaction.user):
            await interaction.response.send_message('このコマンドを実行できる権限がありません。', ephemeral=True)
            return

        target_channel = channel or interaction.channel
        if not isinstance(target_channel, discord.TextChannel) or target_channel.guild.id != guild.id:
            await interaction.response.send_message('このチャンネルはエクスポート対象にできません。', ephemeral=True)
            return

        bounded_limit = min(max(limit or LOG_EXPORT_MAX_MESSAGES, 1), LOG_EXPORT_MAX_MESSAGES)
        bounded_days = min(max(days or LOG_EXPORT_DEFAULT_DAYS, 1), 90)
        now = datetime.datetime.now(datetime.timezone.utc)
        after = now - datetime.timedelta(days=bounded_days)

        await interaction.response.defer(ephemeral=True, thinking=True)

        messages = []
        async for message in target_channel.history(limit=bounded_limit, after=after, oldest_first=True):
            serialized = serialize_message(message)
            if serialized['content'] or serialized['attachments_count'] or serialized['embeds_count']:
                messages.append(serialized)

        payload = {
            'export_version': 1,
            'generated_at': now.isoformat(),
            'source_guild': {
                'id': str(guild.id),
                'name': guild.name,
            },
            'source_channel': {
                'id': str(target_channel.id),
                'name': target_channel.name,
            },
            'bounds': {
                'limit': bounded_limit,
                'days': bounded_days,
                'after': after.isoformat(),
            },
            'privacy': {
                'author': 'sha256(guild_id:user_id) prefix, no raw user id',
                'content': 'message.clean_content with token/email/invite/url redaction',
            },
            'messages': messages,
        }
        body = json.dumps(payload, ensure_ascii=False, indent=2).encode('utf-8')
        filename = f'community-log-{guild.id}-{target_channel.id}-{now.strftime("%Y%m%d%H%M%S")}.json'
        await interaction.followup.send(
            content=f'{len(messages)}件のメッセージを記事化レビュー用JSONとして出力しました。',
            file=discord.File(io.BytesIO(body), filename=filename),
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommunityLogExportCog(bot))
