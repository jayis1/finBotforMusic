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

    @commands.command(name="fetch_and_set_cookies")
    @commands.is_owner()
    async def fetch_and_set_cookies(self, ctx, url: str):
        """Fetches cookies from a given URL and saves them to youtube_cookie.txt for yt-dlp.
        Usage: !fetch_and_set_cookies <URL>
        """
        if not url.startswith("https://"):
            return await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} URL must be HTTPS.", discord.Color.red()))
        logging.info(f"fetch_and_set_cookies command invoked by {ctx.author} for URL: {url}")
        await ctx.send(embed=self.create_embed("Fetching Cookies", f"Attempting to fetch cookies from `{url}`..."))
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    logging.info(f"HTTP GET request to {url} returned status: {response.status}")
                    if response.status != 200:
                        logging.error(f"Failed to fetch URL {url}. Status: {response.status}")
                        return await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} Failed to fetch URL. Status: {response.status}", discord.Color.red()))

                    set_cookie_headers = response.headers.getall('Set-Cookie', [])
                    logging.info(f"Found {len(set_cookie_headers)} 'Set-Cookie' headers.")
                    
                    if not set_cookie_headers:
                        logging.warning(f"No 'Set-Cookie' headers found in response from {url}")
                        return await ctx.send(embed=self.create_embed("No Cookies", f"{config.ERROR_EMOJI} No 'Set-Cookie' headers found in the response from `{url}`.", discord.Color.orange()))

                    cookie_lines = []
                    for header in set_cookie_headers:
                        parsed_cookies = cookie_parser.parse_all_cookies(header)
                        logging.debug(f"Parsed cookies from header: {parsed_cookies}")
                        for name, value in parsed_cookies.items():
                            domain_match = re.search(r'Domain=([^;]+)', header, re.IGNORECASE)
                            domain = domain_match.group(1) if domain_match else ""
                            
                            path_match = re.search(r'Path=([^;]+)', header, re.IGNORECASE)
                            path = path_match.group(1) if path_match else "/"

                            secure = "TRUE" if "Secure" in header else "FALSE"

                            expires_match = re.search(r'Expires=([^;]+)', header, re.IGNORECASE)
                            expiration_timestamp = "0"
                            if expires_match:
                                try:
                                    expires_str = expires_match.group(1).strip()
                                    dt_object = datetime.strptime(expires_str, "%a, %d %b %Y %H:%M:%S %Z")
                                    expiration_timestamp = str(int(dt_object.timestamp()))
                                except ValueError:
                                    logging.warning(f"Could not parse expiration date '{expires_str}' for cookie {name}")
                                    pass

                            flag = "TRUE" if domain.startswith('.') else "FALSE"
                            
                            cookie_line = f"{domain}\t{flag}\t{path}\t{secure}\t{expiration_timestamp}\t{name}\t{value}"
                            cookie_lines.append(cookie_line)

                    if not cookie_lines:
                        logging.warning(f"No parsable cookies found in response from {url}")
                        return await ctx.send(embed=self.create_embed("No Parsable Cookies", f"{config.ERROR_EMOJI} No parsable cookies found in the response from `{url}`.", discord.Color.orange()))

                    with open("youtube_cookie.txt", "w") as f:
                        f.write("# Netscape HTTP Cookie File\n")
                        f.write("\n".join(cookie_lines))
                    logging.info(f"Successfully wrote {len(cookie_lines)} cookie lines to youtube_cookie.txt")
                    
                    from cogs import youtube
                    youtube.YTDL_FORMAT_OPTIONS["cookiefile"] = "youtube_cookie.txt"
                    logging.info("Updated yt_dlp cookiefile option.")

                    await ctx.send(embed=self.create_embed("Cookies Set", f"{config.SUCCESS_EMOJI} Successfully fetched and set cookies from `{url}` to `youtube_cookie.txt`."))

        except aiohttp.ClientError as e:
            logging.error(f"Network error fetching cookies from {url}: {e}")
            await ctx.send(embed=self.create_embed("Network Error", f"{config.ERROR_EMOJI} A network error occurred: {e}", discord.Color.red()))
        except Exception as e:
            logging.error(f"An unexpected error occurred in fetch_and_set_cookies for {url}: {e}", exc_info=True)
            await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} An unexpected error occurred: {e}", discord.Color.red()))

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

    def create_embed(self, title, description, color=discord.Color.blurple()):
        return discord.Embed(title=title, description=description, color=color)

async def setup(bot):
    await bot.add_cog(Admin(bot))
