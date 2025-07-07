import discord
from discord.ext import commands
import config
import re
import aiohttp
from datetime import datetime
import logging

from utils import cookie_parser

class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command(name="cookies_help")
    @commands.is_owner()
    async def cookies_help(self, ctx):
        """Provides instructions on how to use cookies to play private videos."""
        logging.info(f"cookies_help command invoked by {ctx.author}")
        
        embed = discord.Embed(
            title="🍪 How to Use Cookies for Private Videos",
            description="To play private or members-only YouTube videos, the bot needs your browser's login cookies.",
            color=discord.Color.blue()
        )
        embed.add_field(
            name="1. Install a Browser Extension",
            value="Install an extension that can export cookies in the `Netscape` format. A good one for Chrome/Firefox is **'Get cookies.txt LOCALLY'**.",
            inline=False
        )
        embed.add_field(
            name="2. Export Your YouTube Cookies",
            value="Go to `youtube.com`, make sure you are logged in, and use the extension to export your cookies. Save the file.",
            inline=False
        )
        embed.add_field(
            name="3. Create the Cookie File",
            value="Open the exported file, copy its contents, and paste them into a new file named `youtube_cookie.txt` in the bot's main directory.",
            inline=False
        )
        embed.add_field(
            name="4. Restart the Bot",
            value=f"Use the `{config.COMMAND_PREFIX}restart` command to apply the changes. The bot will automatically detect and use the cookie file.",
            inline=False
        )
        embed.set_footer(text="Warning: Your cookies contain sensitive login information. Do not share them.")
        
        await ctx.send(embed=embed)

    @commands.command(name="shutdown")
    @commands.is_owner()
    async def shutdown(self, ctx):
        """Shuts down the bot completely."""
        logging.info(f"Shutdown command invoked by {ctx.author}")
        await ctx.send(embed=self.create_embed("Shutting Down", f"{config.SUCCESS_EMOJI} The bot is now shutting down."))
        await self.bot.close()
        logging.info("Bot has been shut down.")

    @commands.command(name="restart")
    @commands.is_owner()
    async def restart(self, ctx):
        """Restarts the bot."""
        logging.info(f"Restart command invoked by {ctx.author}")
        await ctx.send(embed=self.create_embed("Restarting", f"{config.SUCCESS_EMOJI} The bot is restarting..."))
        await self.bot.close()
        logging.info("Bot is attempting to restart.")

    @commands.command(name="servers")
    @commands.is_owner()
    async def servers(self, ctx):
        """Lists all servers the bot is in."""
        logging.info(f"servers command invoked by {ctx.author}")
        server_list = "\n".join([f"- {s.name} (ID: {s.id})" for s in self.bot.guilds])
        embed = self.create_embed("Servers", f"I am currently in the following servers:\n{server_list}")
        await ctx.send(embed=embed)

    def create_embed(self, title, description, color=discord.Color.blurple()):
        return discord.Embed(title=title, description=description, color=color)

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.CommandOnCooldown):
            await ctx.send("**Try after {0} second ".format(round(error.retry_after, 2)))

async def setup(bot):
    try:
        await bot.add_cog(Admin(bot))
    except Exception as e:
        logging.error(f"Failed to load admin cog: {e}", exc_info=True)
