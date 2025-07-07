import asyncio
import logging
import os
import sys
from discord.ext import tasks, commands
import config
from .db_utils import log_healing_event, initialize_db
from transformers import AutoModelForCausalLM, AutoTokenizer

class SelfHealing(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        initialize_db()
        try:
            self.tokenizer = AutoTokenizer.from_pretrained("distilgpt2")
            self.model = AutoModelForCausalLM.from_pretrained("distilgpt2")
        except Exception as e:
            logging.error(f"Failed to load DistilGPT-2 model: {e}")
            self.model = None
            self.tokenizer = None
        self.health_check.start()

    def cog_unload(self):
        self.health_check.cancel()

    @tasks.loop(seconds=60)
    async def health_check(self):
        # Check if the bot is closed
        if self.bot.is_closed():
            log_healing_event("Bot disconnected", "Attempting to reconnect.")
            try:
                await self.bot.login(config.DISCORD_TOKEN)
                await self.bot.connect()
                log_healing_event("Reconnected successfully.")
            except Exception as e:
                log_healing_event("Reconnect failed", str(e))
                self.restart_bot()

        # Check the Discord gateway latency
        if self.bot.latency > 1.0:
            log_healing_event("High latency detected", f"Latency: {self.bot.latency}")
            await self.bot.close()
            await self.bot.login(config.DISCORD_TOKEN)
            await self.bot.connect()
            log_healing_event("Reconnected due to high latency.")

        # Check if the bot is in a voice channel but not playing anything
        for guild in self.bot.guilds:
            if guild.voice_client and not guild.voice_client.is_playing() and not guild.voice_client.is_paused():
                log_healing_event("Voice client idle", f"In {guild.name} but not playing.")
                await asyncio.sleep(300)
                if guild.voice_client and not guild.voice_client.is_playing() and not guild.voice_client.is_paused():
                    await guild.voice_client.disconnect()
                    log_healing_event("Disconnected due to inactivity.")

    def restart_bot(self):
        log_healing_event("Restarting bot")
        os.execv(sys.executable, ['python'] + sys.argv)

    def generate_error_summary(self, error_message):
        if not self.model or not self.tokenizer:
            return "Local AI model not available. Cannot generate error summary."
        
        prompt = f"Summarize the following Python error and suggest a potential cause:\n\n{error_message}\n\nSummary:"
        try:
            inputs = self.tokenizer(prompt, return_tensors="pt", max_length=512, truncation=True)
            outputs = self.model.generate(**inputs, max_length=100, num_beams=5, early_stopping=True)
            summary = self.tokenizer.decode(outputs[0], skip_special_tokens=True)
            return summary
        except Exception as e:
            logging.error(f"Error generating summary with local AI: {e}")
            return "Failed to generate error summary."

    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        log_healing_event("Command error", f"Command: {ctx.command}, Error: {error}")
        
        error_message = f"Command: {ctx.command}\nError: {error}"
        summary = self.generate_error_summary(str(error))

        response = (
            f"I've encountered an error in the `{ctx.command}` command.\n\n"
            f"**AI-Generated Summary:**\n"
            f"```\n{summary}\n```\n"
            f"Please check the logs for the full traceback."
        )
        
        await ctx.send(response)

async def setup(bot):
    await bot.add_cog(SelfHealing(bot))
