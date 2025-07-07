import os
import inspect
import traceback
from discord.ext import commands
import config
import logging
from transformers import AutoModelForCausalLM, AutoTokenizer

class AIError(Exception):
    """Custom exception for AI-related errors."""
    pass

class AICog(commands.Cog, name="AI"):
    def __init__(self, bot):
        self.bot = bot
        try:
            self.minigpt_tokenizer = AutoTokenizer.from_pretrained("distilgpt2")
            self.minigpt_model = AutoModelForCausalLM.from_pretrained("distilgpt2")
        except Exception as e:
            logging.error(f"Failed to load DistilGPT-2 model: {e}", exc_info=True)
            self.minigpt_model = None
            self.minigpt_tokenizer = None

    @commands.command()
    async def minigpt(self, ctx, *, prompt: str):
        """
        Generates text using a local GPT model.
        """
        if not self.minigpt_model or not self.minigpt_tokenizer:
            await ctx.send("The MiniGPT model is not available. Please check the logs for errors.")
            return

        try:
            inputs = self.minigpt_tokenizer(prompt, return_tensors="pt")
            outputs = self.minigpt_model.generate(**inputs, max_length=50)
            response = self.minigpt_tokenizer.decode(outputs[0], skip_special_tokens=True)
            await ctx.send(response)
        except Exception as e:
            logging.error(f"Error in minigpt command: {e}", exc_info=True)
            await ctx.send("An error occurred while generating text with MiniGPT.")

    @commands.command(name="view_files")
    @commands.is_owner()
    async def view_files(self, ctx, *, path: str = None):
        """
        Lists files and directories at a specified path within the bot's directory.
        Only accessible by the bot owner.
        """
        base_dir = os.path.abspath("/root/.local/LizBotz")
        
        if path:
            # Prevent directory traversal attacks
            requested_path = os.path.abspath(os.path.join(base_dir, path))
            if not requested_path.startswith(base_dir):
                await ctx.send("Access denied: Path is outside the allowed directory.")
                return
        else:
            requested_path = base_dir

        try:
            if not os.path.exists(requested_path):
                await ctx.send(f"Error: Path does not exist: `{requested_path}`")
                return
            
            if not os.path.isdir(requested_path):
                await ctx.send(f"Error: Path is not a directory: `{requested_path}`")
                return

            output = f"Contents of `{requested_path}`:\n```\n"
            items = sorted(os.listdir(requested_path))
            for item in items:
                item_path = os.path.join(requested_path, item)
                if os.path.isdir(item_path):
                    output += f"[D] {item}/\n"
                else:
                    output += f"[F] {item}\n"
            output += "```"
            
            if len(output) > 2000:
                await ctx.send("Output is too long to display. Please specify a more specific path.")
            else:
                await ctx.send(output)

        except Exception as e:
            logging.error(f"Error in view_files command: {e}", exc_info=True)
            await ctx.send(f"An error occurred: {e}")


    @commands.Cog.listener()
    async def on_command_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"You're missing a required argument: `{error.param.name}`")
        elif isinstance(error, commands.CommandInvokeError) and isinstance(error.original, AIError):
            # This is handled in the command itself, but we can add a general fallback.
            pass
        else:
            logging.error(f"Unhandled command error in AICog: {error}", exc_info=True)
            
async def setup(bot):
    try:
        await bot.add_cog(AICog(bot))
    except Exception as e:
        logging.error(f"Failed to load ai cog: {e}", exc_info=True)
