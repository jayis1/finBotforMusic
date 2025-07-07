# config.py

# It is recommended to use environment variables for sensitive data.
# However, you can hardcode the values here for simplicity.
import os
from dotenv import load_dotenv

load_dotenv()

DISCORD_TOKEN = os.environ.get("DISCORD_TOKEN")
YOUTUBE_API_KEY = os.environ.get("YOUTUBE_API_KEY")
BOT_OWNER_ID = int(os.environ.get("BOT_OWNER_ID"))

# You can change the bot's command prefix here
COMMAND_PREFIX = "?"

# Emojis for UI
PLAY_EMOJI = '▶️'
PAUSE_EMOJI = '⏸️'
SKIP_EMOJI = '⏭️'
QUEUE_EMOJI = '🎵'
ERROR_EMOJI = '❌'
SUCCESS_EMOJI = '✅'

# Discord Channel ID for sending bot logs (errors, warnings)
LOG_CHANNEL_ID = int(os.environ.get("LOG_CHANNEL_ID"))


