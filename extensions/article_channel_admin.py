import asyncio
import datetime
import io
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

from constant import ARTICLE_CHANNEL_AUDIT_GUILD_IDS
from constant import ARTICLE_CHANNEL_AUDIT_MIN_SCORE
from constant import ARTICLE_CHANNEL_AUDIT_OPERATOR_ROLE_IDS
from constant import ARTICLE_CHANNEL_AUDIT_REPORT_CHANNEL_ID
from constant import ARTICLE_CHANNEL_AUDIT_STARTUP_MODE
from constant import GUILD_ID
from constant import GUILD_LOGS_ID
from utils.dpyexcept import excepter


ARTICLE_CATEGORY_PREFIX = '記事化対象:'
SUPPORTED_CHANNEL_TYPES = (discord.TextChannel, discord.ForumChannel)
STARTUP_MODES = {'off', 'dry_run'}


@dataclass(frozen=True)
class ArticleCategoryRule:
    name: str
    keywords: tuple[str, ...]


ARTICLE_CATEGORY_RULES = (
    ArticleCategoryRule(
        '記事化対象: discord.py / Python',
        (
            'discord.py',
            'discordpy',
            'dpy',
            'python',
            'pycord',
            'nextcord',
            'disnake',
            'aiohttp',
            'cog',
            'extension',
        ),
    ),
    ArticleCategoryRule(
        '記事化対象: discord.js / Node.js',
        (
            'discord.js',
            'discordjs',
            'djs',
            'node',
            'node.js',
            'javascript',
            'typescript',
            'js',
            'ts',
            'npm',
            'yarn',
        ),
    ),
    ArticleCategoryRule(
        '記事化対象: API・権限・Developer Portal',
        (
            'api',
            'gateway',
            'intent',
            'intents',
            'oauth',
            'oauth2',
            'permission',
            'permissions',
            '権限',
            '認可',
            '認証',
            'developer portal',
            'dev portal',
            '開発者ポータル',
            'アプリケーション',
        ),
    ),
    ArticleCategoryRule(
        '記事化対象: Interaction・UI',
        (
            'slash',
            'スラッシュ',
            'interaction',
            'interactions',
            'command',
            'commands',
            'コマンド',
            'component',
            'components',
            'button',
            'select',
            'modal',
            'embed',
            'ui',
            'ボタン',
            'セレクト',
            'モーダル',
            '埋め込み',
        ),
    ),
    ArticleCategoryRule(
        '記事化対象: 運用・ホスティング',
        (
            'deploy',
            'deployment',
            'hosting',
            'host',
            'railway',
            'heroku',
            'render',
            'fly.io',
            'docker',
            'vps',
            'server',
            'サーバー',
            'デプロイ',
            'ホスティング',
            '運用',
            '常時起動',
        ),
    ),
    ArticleCategoryRule(
        '記事化対象: エラー・トラブルシュート',
        (
            'error',
            'errors',
            'exception',
            'traceback',
            'bug',
            'debug',
            'trouble',
            'fix',
            'エラー',
            '例外',
            '不具合',
            'バグ',
            'デバッグ',
            'トラブル',
            '解決',
        ),
    ),
    ArticleCategoryRule(
        '記事化対象: ログ・事例アーカイブ',
        (
            'log',
            'logs',
            'archive',
            'case',
            'cases',
            'knowledge',
            'faq',
            'tips',
            'ログ',
            'アーカイブ',
            '事例',
            'ナレッジ',
            'faq',
            'tips',
            '小ネタ',
        ),
    ),
    ArticleCategoryRule(
        '記事化対象: Bot開発総合',
        (
            'bot',
            'bots',
            'discordbot',
            'discord bot',
            'discord-bot',
            'ボット',
            'bot開発',
            'bot制作',
            'bot運用',
            '開発',
            '制作',
            '実装',
            '相談',
            '質問',
            'qa',
            'q&a',
            'help',
            'ヘルプ',
        ),
    ),
)

CORE_CANDIDATE_TERMS = (
    'bot',
    'bots',
    'discordbot',
    'discord bot',
    'discord-bot',
    'ボット',
    'bot開発',
    'bot制作',
    'bot運用',
    '開発',
    '制作',
    '実装',
)

EXCLUDE_TERMS = (
    'rule',
    'rules',
    'welcome',
    'announce',
    'announcement',
    'notice',
    'mod',
    'moderator',
    'admin',
    'staff',
    '運営',
    '管理',
    '規約',
    '告知',
    '案内',
    '挨拶',
    '入退室',
    'join',
    'leave',
)

SPECIFIC_ARTICLE_TERMS = {
    'discord.py',
    'discordpy',
    'dpy',
    'python',
    'pycord',
    'nextcord',
    'disnake',
    'discord.js',
    'discordjs',
    'djs',
    'node.js',
    'typescript',
    'gateway',
    'intent',
    'intents',
    'oauth',
    'oauth2',
    'permission',
    'permissions',
    '権限',
    'developer portal',
    'dev portal',
    '開発者ポータル',
    'slash',
    'スラッシュ',
    'interaction',
    'interactions',
    'component',
    'components',
    'modal',
    'embed',
    'deploy',
    'deployment',
    'railway',
    'heroku',
    'render',
    'fly.io',
    'docker',
    'vps',
    'デプロイ',
    'ホスティング',
    '常時起動',
    'error',
    'errors',
    'exception',
    'traceback',
    'debug',
    'エラー',
    '例外',
    'デバッグ',
}


def has_audit_permission(member: discord.Member) -> bool:
    if member.guild.owner_id == member.id:
        return True
    if member.guild_permissions.manage_channels:
        return True
    role_ids = {role.id for role in member.roles}
    return any(role_id in role_ids for role_id in ARTICLE_CHANNEL_AUDIT_OPERATOR_ROLE_IDS)


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize('NFKC', value or '').lower()
    return re.sub(r'\s+', ' ', normalized).strip()


def compact_text(value: str) -> str:
    return re.sub(r'[\s_\-./・]+', '', value)


def has_term(context: str, compact_context: str, term: str) -> bool:
    normalized_term = normalize_text(term)
    compacted_term = compact_text(normalized_term)
    if len(compacted_term) <= 3 and re.fullmatch(r'[a-z0-9]+', compacted_term):
        return re.search(rf'(?<![a-z0-9]){re.escape(normalized_term)}(?![a-z0-9])', context) is not None
    if normalized_term in context:
        return True
    return compacted_term in compact_context


def collect_channel_context(channel: discord.abc.GuildChannel) -> str:
    parts = [channel.name]
    category = getattr(channel, 'category', None)
    if category is not None:
        parts.append(category.name)
    topic = getattr(channel, 'topic', None)
    if topic:
        parts.append(topic)
    tags = getattr(channel, 'available_tags', None)
    if tags:
        parts.extend(tag.name for tag in tags)
    return normalize_text(' '.join(parts))


def channel_type_name(channel: discord.abc.GuildChannel) -> str:
    if isinstance(channel, discord.ForumChannel):
        return 'forum'
    if isinstance(channel, discord.TextChannel):
        return 'text'
    return channel.__class__.__name__


def current_category_name(channel: discord.abc.GuildChannel) -> Optional[str]:
    category = getattr(channel, 'category', None)
    return category.name if category is not None else None


def classify_channel(channel: discord.abc.GuildChannel, min_score: int) -> Optional[dict]:
    if not isinstance(channel, SUPPORTED_CHANNEL_TYPES):
        return None

    context = collect_channel_context(channel)
    compact_context = compact_text(context)
    category_name = current_category_name(channel)
    if category_name and category_name.startswith(ARTICLE_CATEGORY_PREFIX):
        return {
            'category': category_name,
            'score': 999,
            'reason_terms': ['already-in-article-category'],
        }

    excluded = [term for term in EXCLUDE_TERMS if has_term(context, compact_context, term)]
    core_hits = [term for term in CORE_CANDIDATE_TERMS if has_term(context, compact_context, term)]

    best_rule = None
    best_hits: list[str] = []
    general_rule = ARTICLE_CATEGORY_RULES[-1]
    general_hits = [term for term in general_rule.keywords if has_term(context, compact_context, term)]
    for rule in ARTICLE_CATEGORY_RULES[:-1]:
        hits = [term for term in rule.keywords if has_term(context, compact_context, term)]
        if len(hits) > len(best_hits):
            best_rule = rule
            best_hits = hits
    if not best_rule and general_hits:
        best_rule = general_rule
        best_hits = general_hits

    specific_hits = [term for term in best_hits if term in SPECIFIC_ARTICLE_TERMS]
    score = len(core_hits) * 2 + len(specific_hits) * 2 + (len(best_hits) - len(specific_hits))
    if excluded and not core_hits and not best_hits:
        return None
    if not core_hits and not specific_hits and len(best_hits) < 2:
        return None
    if not best_rule or score < min_score:
        return None

    return {
        'category': best_rule.name,
        'score': score,
        'reason_terms': sorted(set(core_hits + best_hits)),
    }


def build_audit_records(guild: discord.Guild, min_score: int) -> list[dict]:
    records = []
    for channel in sorted(guild.channels, key=lambda item: item.position):
        classification = classify_channel(channel, min_score)
        if classification is None:
            continue
        records.append(
            {
                'channel_id': str(channel.id),
                'channel_name': channel.name,
                'channel_type': channel_type_name(channel),
                'current_category': current_category_name(channel),
                'target_category': classification['category'],
                'score': classification['score'],
                'reason_terms': classification['reason_terms'],
                'actions': [],
            }
        )
    return records


def everyone_view_is_off(target, guild: discord.Guild) -> bool:
    return target.overwrites_for(guild.default_role).view_channel is False


def build_planned_changes(guild: discord.Guild, records: list[dict]) -> dict:
    category_actions: dict[str, list[str]] = {}
    categories: dict[str, Optional[discord.CategoryChannel]] = {
        category.name: category for category in guild.categories
    }

    for category_name in sorted({record['target_category'] for record in records}):
        actions = []
        category = categories.get(category_name)
        if category is None:
            actions.append('create-category')
            actions.append('category-everyone-view-off')
        elif not everyone_view_is_off(category, guild):
            actions.append('category-everyone-view-off')
        category_actions[category_name] = actions

    for record in records:
        channel = guild.get_channel(int(record['channel_id']))
        if not isinstance(channel, SUPPORTED_CHANNEL_TYPES):
            record['actions'].append('skip-channel-not-found')
            continue

        if not everyone_view_is_off(channel, guild):
            record['actions'].append('channel-everyone-view-off')

        target_category_name = current_category_name(channel)
        if target_category_name != record['target_category']:
            record['actions'].append('move-to-category')

    return {
        'categories': category_actions,
        'records': records,
    }


async def audit_guild(guild: discord.Guild, min_score: int) -> dict:
    records = build_audit_records(guild, min_score)
    result = build_planned_changes(guild, records)
    return {
        'guild_id': str(guild.id),
        'guild_name': guild.name,
        'mode': 'dry_run',
        'min_score': min_score,
        'matched_channels': len(records),
        **result,
    }


def build_markdown_report(payload: dict) -> str:
    lines = [
        '# 記事化対象チャンネル棚卸し',
        '',
        f"- generated_at: {payload['generated_at']}",
        f"- mode: {payload['mode']}",
        '',
    ]
    for guild_result in payload['guilds']:
        lines.extend(
            [
                f"## {guild_result['guild_name']} ({guild_result['guild_id']})",
                f"- matched_channels: {guild_result['matched_channels']}",
                '',
            ]
        )
        if guild_result.get('error'):
            lines.extend([f"- error: {guild_result['error']}", ''])
        grouped: dict[str, list[dict]] = {}
        for record in guild_result['records']:
            grouped.setdefault(record['target_category'], []).append(record)

        for category_name in sorted(grouped):
            lines.append(f'### {category_name}')
            category_actions = guild_result['categories'].get(category_name) or []
            if category_actions:
                lines.append(f"- category_actions: {', '.join(category_actions)}")
            for record in grouped[category_name]:
                current = record['current_category'] or '未分類'
                actions = ', '.join(record['actions']) if record['actions'] else 'no-change'
                reasons = ', '.join(record['reason_terms'])
                lines.append(
                    f"- #{record['channel_name']} ({record['channel_type']}, from: {current}, score: {record['score']})"
                    f" / reasons: {reasons} / actions: {actions}"
                )
            lines.append('')
    return '\n'.join(lines)


def build_summary(payload: dict) -> str:
    total = sum(result['matched_channels'] for result in payload['guilds'])
    per_guild = ', '.join(f"{result['guild_name']}: {result['matched_channels']}" for result in payload['guilds'])
    return f'確認モードで記事化対象チャンネルを棚卸ししました。対象: {total}件 ({per_guild})'


def build_report_file(payload: dict) -> discord.File:
    report = build_markdown_report(payload)
    body = report.encode('utf-8')
    filename = f"article-channel-audit-{payload['generated_at_file']}.md"
    return discord.File(io.BytesIO(body), filename=filename)


class ArticleChannelAdminCog(commands.Cog):
    """記事化対象チャンネルの棚卸しと非公開カテゴリ化"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._startup_task: Optional[asyncio.Task] = None

    async def cog_load(self) -> None:
        self._startup_task = asyncio.create_task(self.run_startup_audit())

    async def cog_unload(self) -> None:
        if self._startup_task is not None:
            self._startup_task.cancel()

    async def run_startup_audit(self) -> None:
        mode = ARTICLE_CHANNEL_AUDIT_STARTUP_MODE if ARTICLE_CHANNEL_AUDIT_STARTUP_MODE in STARTUP_MODES else 'off'
        if mode == 'off':
            return

        await self.bot.wait_until_ready()
        await asyncio.sleep(5)
        payload = await self.run_audit_for_allowed_guilds(ARTICLE_CHANNEL_AUDIT_MIN_SCORE)
        print(json.dumps({**payload, 'report': build_markdown_report(payload)}, ensure_ascii=False))

        report_channel = self.bot.get_channel(ARTICLE_CHANNEL_AUDIT_REPORT_CHANNEL_ID)
        if report_channel is None:
            try:
                report_channel = await self.bot.fetch_channel(ARTICLE_CHANNEL_AUDIT_REPORT_CHANNEL_ID)
            except discord.DiscordException:
                report_channel = None
        if isinstance(report_channel, discord.abc.Messageable):
            await report_channel.send(content=build_summary(payload), file=build_report_file(payload))

    async def run_audit_for_allowed_guilds(self, min_score: int) -> dict:
        now = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            'generated_at': now.isoformat(),
            'generated_at_file': now.strftime('%Y%m%d%H%M%S'),
            'mode': 'dry_run',
            'guilds': [],
        }
        for guild_id in ARTICLE_CHANNEL_AUDIT_GUILD_IDS:
            guild = self.bot.get_guild(guild_id)
            if guild is None:
                payload['guilds'].append(
                    {
                        'guild_id': str(guild_id),
                        'guild_name': 'unknown',
                        'mode': payload['mode'],
                        'min_score': min_score,
                        'matched_channels': 0,
                        'categories': {},
                        'records': [],
                        'error': 'guild-not-found',
                    }
                )
                continue
            payload['guilds'].append(await audit_guild(guild, min_score))
        return payload

    @app_commands.command(name='記事化チャンネル棚卸し', description='Bot開発情報チャンネルを記事化対象カテゴリへ分類します')
    @app_commands.guilds(discord.Object(id=GUILD_ID), discord.Object(id=GUILD_LOGS_ID))
    @app_commands.guild_only()
    @excepter
    async def audit_article_channels(
        self,
        interaction: discord.Interaction,
        min_score: Optional[int] = None,
    ):
        guild = interaction.guild
        if guild is None or guild.id not in ARTICLE_CHANNEL_AUDIT_GUILD_IDS:
            await interaction.response.send_message('このサーバーでは記事化チャンネル棚卸しを利用できません。', ephemeral=True)
            return
        if not isinstance(interaction.user, discord.Member) or not has_audit_permission(interaction.user):
            await interaction.response.send_message('このコマンドを実行できる権限がありません。', ephemeral=True)
            return

        await interaction.response.defer(ephemeral=True, thinking=True)
        bounded_min_score = min(max(min_score or ARTICLE_CHANNEL_AUDIT_MIN_SCORE, 1), 10)
        result = await audit_guild(guild, bounded_min_score)
        now = datetime.datetime.now(datetime.timezone.utc)
        payload = {
            'generated_at': now.isoformat(),
            'generated_at_file': now.strftime('%Y%m%d%H%M%S'),
            'mode': 'dry_run',
            'guilds': [result],
        }
        await interaction.followup.send(content=build_summary(payload), file=build_report_file(payload), ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ArticleChannelAdminCog(bot))
