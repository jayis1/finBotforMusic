import asyncio
import discord
from discord.ext import commands
import logging
import time

import config
from .youtube import YTDLSource, FFMPEG_OPTIONS

class Player(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    try:
        await bot.add_cog(Player(bot))
    except Exception as e:
        logging.error(f"Failed to load player cog: {e}", exc_info=True)
