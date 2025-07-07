#!/usr/bin/env python3
import asyncio
import os
import discord
from discord.ext import commands
import config
import logging
from utils.discord_log_handler import DiscordLogHandler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s:%(levelname)s:%(name)s: %(message)s',
    handlers=[
        logging.FileHandler("bot_activity.log"),
        logging.StreamHandler() # Keep StreamHandler for console output
    ]
)

intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True

bot = commands.Bot(command_prefix=config.COMMAND_PREFIX, intents=intents, owner_id=config.BOT_OWNER_ID)

discord_log_handler = None # Initialize as None, will be set in on_ready

@bot.event
async def on_ready():
    global discord_log_handler
    logging.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    logging.info(f"Intents: {bot.intents}")
    logging.info('------')

    # Initialize and add DiscordLogHandler after bot is ready
    if config.LOG_CHANNEL_ID and config.LOG_CHANNEL_ID != "YOUR_LOG_CHANNEL_ID":
        discord_log_handler = DiscordLogHandler(bot, config.LOG_CHANNEL_ID)
        logging.getLogger().addHandler(discord_log_handler) # Add to root logger
        logging.info(f"Discord log handler added for channel ID: {config.LOG_CHANNEL_ID}")
    else:
        logging.warning("LOG_CHANNEL_ID is not set in config.py. Discord logging will be disabled.")

async def main():
    # Create an audio cache directory
    audio_cache_dir = "audio_cache"
    if not os.path.exists(audio_cache_dir):
        os.makedirs(audio_cache_dir)
        logging.info(f"Created audio cache directory: {audio_cache_dir}")
    else:
        logging.info(f"Audio cache directory already exists: {audio_cache_dir}")

    # The yt_dlp_cache directory is no longer strictly necessary for streaming,
    # but can be kept if yt-dlp still uses it for other metadata caching.
    # For now, we'll keep it as it doesn't harm anything.
    cache_dir = "yt_dlp_cache"
    if not os.path.exists(cache_dir):
        os.makedirs(cache_dir)
        logging.info(f"Created yt-dlp cache directory: {cache_dir}")
    else:
        logging.info(f"yt-dlp cache directory already exists: {cache_dir}")

    async with bot:
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py') and filename != '__init__.py' and filename != 'youtube.py' and filename != 'logging.py':
                try:
                    await bot.load_extension(f'cogs.{filename[:-3]}')
                    logging.info(f'Successfully loaded extension: {filename}')
                except Exception as e:
                    logging.error(f'Failed to load extension {filename}: {e}')
        
        try:
            await bot.load_extension('cogs.ai')
            logging.info('Successfully loaded extension: ai.py')
        except Exception as e:
            logging.error(f'Failed to load extension ai.py: {e}')
        
        try:
            await bot.start(config.DISCORD_TOKEN)
        except discord.errors.LoginFailure:
            logging.error("Error: Invalid Discord Token. Please check your DISCORD_TOKEN in config.py.")
        except Exception as e:
            logging.error(f"Error when starting bot: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped.")
