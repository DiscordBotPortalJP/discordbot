from dotenv import load_dotenv
from os import getenv

load_dotenv()

TOKEN = getenv('DISCORD_BOT_TOKEN')
APPLICATION_ID = getenv('APPLICATION_ID', 463011721058058240)
GUILD_ID = int(getenv('GUILD_ID', 494911447420108820))
LOG_CHANNEL_ID = int(getenv('LOG_CHANNEL_ID', 1063508527575998494))
