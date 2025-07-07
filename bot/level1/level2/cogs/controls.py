import discord
from discord.ext import commands
import logging
import time

import config

class Controls(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    try:
        await bot.add_cog(Controls(bot))
    except Exception as e:
        logging.error(f"Failed to load controls cog: {e}", exc_info=True)