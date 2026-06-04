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
from constant import LOG_EXPORT_BULK_DEFAULT_DAYS
from constant import LOG_EXPORT_BULK_MAX_CHANNELS
from constant import LOG_EXPORT_BULK_MAX_DAYS
from constant import LOG_EXPORT_BULK_MAX_FORUM_THREADS
from constant import LOG_EXPORT_BULK_MAX_MESSAGES_PER_SOURCE
from constant import LOG_EXPORT_GUILD_IDS
from constant import LOG_EXPORT_MAX_MESSAGES
from constant import LOG_EXPORT_OPERATOR_ROLE_IDS
from constant import GUILD_ID
from constant import GUILD_LOGS_ID
from utils.dpyexcept import excepter


TOKEN_PATTERNS = (
    re.compile(r'mfa\.[A-Za-z0-9_-]{20,}'),
    re.compile(r'[A-Za-z0-9_-]{20,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{20,}'),
)
EMAIL_PATTERN = re.compile(r'[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}', re.IGNORECASE)
DISCORD_INVITE_PATTERN = re.compile(r'https?://(?:discord\.gg|discord\.com/invite)/\S+', re.IGNORECASE)
URL_PATTERN = re.compile(r'https?://\S+', re.IGNORECASE)
BULK_ATTACHMENT_BYTE_LIMIT = 24 * 1024 * 1024
BULK_SUPPORTED_CHANNEL_TYPES = (discord.TextChannel, discord.ForumChannel)
PORTAL_TARGET_MARK = '✅'


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


def clamp_int(value: Optional[int], default: int, minimum: int, maximum: int) -> int:
    return min(max(value or default, minimum), maximum)


def bulk_channel_type(channel: discord.abc.GuildChannel) -> str:
    if isinstance(channel, discord.ForumChannel):
        return 'forum'
    if isinstance(channel, discord.TextChannel):
        return 'text'
    return channel.__class__.__name__


def category_name(channel: discord.abc.GuildChannel) -> Optional[str]:
    category = getattr(channel, 'category', None)
    return category.name if category is not None else None


def channel_sort_key(channel: discord.abc.GuildChannel) -> tuple[int, int, int]:
    category = getattr(channel, 'category', None)
    category_position = category.position if category is not None else -1
    return (category_position, getattr(channel, 'position', 0), channel.id)


def is_bulk_target(channel: discord.abc.GuildChannel, guild_id: int) -> bool:
    if not isinstance(channel, BULK_SUPPORTED_CHANNEL_TYPES):
        return False
    if guild_id == GUILD_ID:
        name = category_name(channel)
        return name is not None and PORTAL_TARGET_MARK in name
    if guild_id == GUILD_LOGS_ID:
        return True
    return False


def select_bulk_channels(guild: discord.Guild, max_channels: int) -> list[discord.abc.GuildChannel]:
    channels = [channel for channel in guild.channels if is_bulk_target(channel, guild.id)]
    return sorted(channels, key=channel_sort_key)[:max_channels]


def source_payload(
    guild: discord.Guild,
    channel_id: int,
    channel_name: str,
    channel_type: str,
    parent_channel: Optional[discord.abc.GuildChannel] = None,
) -> dict:
    payload = {
        'id': str(channel_id),
        'name': channel_name,
        'type': channel_type,
    }
    if parent_channel is not None:
        payload['parent_channel_id'] = str(parent_channel.id)
        payload['parent_channel_name'] = parent_channel.name
        payload['category_name'] = category_name(parent_channel)
    else:
        channel = guild.get_channel(channel_id)
        if isinstance(channel, discord.abc.GuildChannel):
            payload['category_name'] = category_name(channel)
    return payload


async def export_message_history(
    source,
    guild: discord.Guild,
    source_channel: dict,
    limit: int,
    after: datetime.datetime,
) -> tuple[dict, Optional[dict]]:
    messages = []
    try:
        raw_messages = []
        async for message in source.history(limit=limit, after=after, oldest_first=False):
            raw_messages.append(message)
        for message in reversed(raw_messages):
            serialized = serialize_message(message)
            serialized['channel_id'] = source_channel['id']
            serialized['channel_name'] = source_channel['name']
            serialized['source_channel_type'] = source_channel['type']
            if serialized['content'] or serialized['attachments_count'] or serialized['embeds_count']:
                messages.append(serialized)
    except discord.Forbidden:
        return (
            {
                'source_guild': {'id': str(guild.id), 'name': guild.name},
                'source_channel': source_channel,
                'messages': [],
            },
            {
                'guild_id': str(guild.id),
                'channel_id': source_channel['id'],
                'channel_name': source_channel['name'],
                'error': 'forbidden',
            },
        )
    except discord.DiscordException as error:
        return (
            {
                'source_guild': {'id': str(guild.id), 'name': guild.name},
                'source_channel': source_channel,
                'messages': [],
            },
            {
                'guild_id': str(guild.id),
                'channel_id': source_channel['id'],
                'channel_name': source_channel['name'],
                'error': error.__class__.__name__,
            },
        )
    return (
        {
            'source_guild': {'id': str(guild.id), 'name': guild.name},
            'source_channel': source_channel,
            'messages': messages,
        },
        None,
    )


async def iter_forum_threads(channel: discord.ForumChannel, max_threads: int):
    seen = set()
    for thread in sorted(channel.threads, key=lambda item: item.created_at or datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)):
        seen.add(thread.id)
        yield thread
        if len(seen) >= max_threads:
            return

    try:
        async for thread in channel.archived_threads(limit=max_threads):
            if thread.id in seen:
                continue
            seen.add(thread.id)
            yield thread
            if len(seen) >= max_threads:
                return
    except discord.DiscordException:
        return


async def export_bulk_channel(
    guild: discord.Guild,
    channel: discord.abc.GuildChannel,
    limit_per_source: int,
    max_forum_threads: int,
    after: datetime.datetime,
) -> tuple[list[dict], list[dict]]:
    exports = []
    errors = []
    if isinstance(channel, discord.TextChannel):
        source = source_payload(guild, channel.id, channel.name, 'text')
        export, error = await export_message_history(channel, guild, source, limit_per_source, after)
        exports.append(export)
        if error:
            errors.append(error)
    elif isinstance(channel, discord.ForumChannel):
        thread_count = 0
        async for thread in iter_forum_threads(channel, max_forum_threads):
            thread_count += 1
            source = source_payload(
                guild,
                thread.id,
                f'{channel.name}/{thread.name}',
                'forum-thread',
                parent_channel=channel,
            )
            export, error = await export_message_history(thread, guild, source, limit_per_source, after)
            exports.append(export)
            if error:
                errors.append(error)
        if thread_count == 0:
            exports.append(
                {
                    'source_guild': {'id': str(guild.id), 'name': guild.name},
                    'source_channel': source_payload(guild, channel.id, channel.name, 'forum'),
                    'messages': [],
                }
            )
    return exports, errors


async def build_bulk_export_payload(
    bot: commands.Bot,
    guild_ids: list[int],
    days: int,
    limit_per_source: int,
    max_channels: int,
    max_forum_threads: int,
) -> dict:
    now = datetime.datetime.now(datetime.timezone.utc)
    after = now - datetime.timedelta(days=days)
    payload = {
        'export_version': 2,
        'generated_at': now.isoformat(),
        'targeting': {
            str(GUILD_ID): f'category name contains {PORTAL_TARGET_MARK}',
            str(GUILD_LOGS_ID): 'all text/forum channels',
        },
        'bounds': {
            'days': days,
            'after': after.isoformat(),
            'limit_per_source': limit_per_source,
            'max_channels_per_guild': max_channels,
            'max_forum_threads_per_channel': max_forum_threads,
        },
        'privacy': {
            'author': 'sha256(guild_id:user_id) prefix, no raw user id',
            'content': 'message.clean_content with token/email/invite/url redaction',
            'attachments': 'attachment URLs are not exported; only counts are included',
        },
        'exports': [],
        'errors': [],
    }
    for guild_id in guild_ids:
        guild = bot.get_guild(guild_id)
        if guild is None:
            payload['errors'].append({'guild_id': str(guild_id), 'error': 'guild-not-found'})
            continue
        for channel in select_bulk_channels(guild, max_channels):
            exports, errors = await export_bulk_channel(
                guild,
                channel,
                limit_per_source,
                max_forum_threads,
                after,
            )
            payload['exports'].extend(exports)
            payload['errors'].extend(errors)
    payload['summary'] = {
        'source_count': len(payload['exports']),
        'message_count': sum(len(item['messages']) for item in payload['exports']),
        'error_count': len(payload['errors']),
    }
    return payload


def build_bulk_export_file(payload: dict) -> tuple[Optional[discord.File], int]:
    body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    if len(body) > BULK_ATTACHMENT_BYTE_LIMIT:
        return None, len(body)
    generated_at = datetime.datetime.fromisoformat(payload['generated_at'])
    filename = f'community-log-bulk-{generated_at.strftime("%Y%m%d%H%M%S")}.json'
    return discord.File(io.BytesIO(body), filename=filename), len(body)


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

    @app_commands.command(name='ログ記事化一括エクスポート', description='指定ルールに沿って記事化レビュー用ログを一括JSON出力します')
    @app_commands.guilds(discord.Object(id=GUILD_ID), discord.Object(id=GUILD_LOGS_ID))
    @app_commands.guild_only()
    @excepter
    async def export_bulk_logs_for_articles(
        self,
        interaction: discord.Interaction,
        all_guilds: bool = True,
        days: Optional[int] = None,
        limit_per_source: Optional[int] = None,
        max_channels: Optional[int] = None,
        max_forum_threads: Optional[int] = None,
    ):
        guild = interaction.guild
        if guild is None or guild.id not in LOG_EXPORT_GUILD_IDS:
            await interaction.response.send_message('このサーバーではログ記事化一括エクスポートを利用できません。', ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not has_export_permission(interaction.user):
            await interaction.response.send_message('このコマンドを実行できる権限がありません。', ephemeral=True)
            return

        bounded_days = clamp_int(days, LOG_EXPORT_BULK_DEFAULT_DAYS, 1, LOG_EXPORT_BULK_MAX_DAYS)
        bounded_limit = clamp_int(limit_per_source, LOG_EXPORT_BULK_MAX_MESSAGES_PER_SOURCE, 1, LOG_EXPORT_BULK_MAX_MESSAGES_PER_SOURCE)
        bounded_channels = clamp_int(max_channels, LOG_EXPORT_BULK_MAX_CHANNELS, 1, LOG_EXPORT_BULK_MAX_CHANNELS)
        bounded_threads = clamp_int(max_forum_threads, LOG_EXPORT_BULK_MAX_FORUM_THREADS, 1, LOG_EXPORT_BULK_MAX_FORUM_THREADS)
        guild_ids = LOG_EXPORT_GUILD_IDS if all_guilds else [guild.id]

        await interaction.response.defer(ephemeral=True, thinking=True)
        payload = await build_bulk_export_payload(
            self.bot,
            guild_ids,
            bounded_days,
            bounded_limit,
            bounded_channels,
            bounded_threads,
        )
        export_file, byte_size = build_bulk_export_file(payload)
        summary = payload['summary']
        if export_file is None:
            await interaction.followup.send(
                content=(
                    '一括エクスポート結果がDiscord添付の安全上限を超えました。'
                    f"現在サイズ: {byte_size} bytes / ソース: {summary['source_count']} / メッセージ: {summary['message_count']}。"
                    '`days`、`limit_per_source`、`max_channels`、`max_forum_threads` を下げて再実行してください。'
                ),
                ephemeral=True,
            )
            return

        await interaction.followup.send(
            content=(
                '記事化レビュー用の一括ログJSONを出力しました。'
                f"ソース: {summary['source_count']} / メッセージ: {summary['message_count']} / エラー: {summary['error_count']}。"
                f'JPはカテゴリ名に {PORTAL_TARGET_MARK} を含むチャンネル、Logsはテキスト/フォーラム全体を対象にしています。'
            ),
            file=export_file,
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(CommunityLogExportCog(bot))
