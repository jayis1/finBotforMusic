import discord
from discord.ext import commands

class Meme(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.channel)
    async def meme(self, ctx):
        await ctx.send("Memes")

async def setup(bot):
    await bot.add_cog(Meme(bot))
