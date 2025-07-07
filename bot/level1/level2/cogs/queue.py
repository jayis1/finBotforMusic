import discord
from discord.ext import commands
import logging

class Queue(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

async def setup(bot):
    try:
        await bot.add_cog(Queue(bot))
    except Exception as e:
        logging.error(f"Failed to load queue cog: {e}", exc_info=True)