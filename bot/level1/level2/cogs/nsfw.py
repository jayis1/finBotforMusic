import discord
from discord.ext import commands

class Nsfw(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.cooldown(1, 10, commands.BucketType.channel)
    async def nsfw(self, ctx):
        if ctx.channel.is_nsfw():
            print("nsfw work!!")
        else:
            print("You can use this command in a nsfw channel only !")

async def setup(bot):
    await bot.add_cog(Nsfw(bot))
