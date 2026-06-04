import discord
from discord.ext import commands
from constant import TOKEN
from constant import GUILD_ID
from constant import GUILD_LOGS_ID

extensions = (
    'auto_reaction',
    'community_log_export',
    'favorite',
    'join',
    'leave',
    'notion',
    'scrapbox',
    'su',
)

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix=commands.when_mentioned_or('$ '),
            help_command=None,
            intents=discord.Intents.all(),
        )

    async def setup_hook(self):
        for extension in extensions:
            await self.load_extension(f'extensions.{extension}')
        for guild_id in (GUILD_ID, GUILD_LOGS_ID):
            await self.tree.sync(guild=discord.Object(id=guild_id))
        await self.tree.sync()

def main():
    MyBot().run(TOKEN)


if __name__ == '__main__':
    main()
