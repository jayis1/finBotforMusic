import logging
import asyncio
import discord

class DiscordLogHandler(logging.Handler):
    def __init__(self, bot_instance, log_channel_id, level=logging.INFO):
        super().__init__(level)
        self.bot = bot_instance
        self.log_channel_id = log_channel_id
        self.queue = asyncio.Queue()
        self.task = None
        self.buffer = []
        self.buffer_lock = asyncio.Lock()
        self.flush_interval = 5  # seconds

    def emit(self, record):
        self.buffer.append(self.format(record))
        if self.task is None or self.task.done():
            self.task = self.bot.loop.create_task(self.flush_buffer())

    async def flush_buffer(self):
        await asyncio.sleep(self.flush_interval)
        async with self.buffer_lock:
            if not self.buffer:
                return

            messages_to_send = self.buffer[:]
            self.buffer.clear()

            if not self.bot.is_ready():
                # If bot is not ready, put messages back to be sent later
                self.buffer.extend(messages_to_send)
                return

            channel = self.bot.get_channel(self.log_channel_id)
            if channel:
                try:
                    # Send messages in chunks if too long
                    full_message = "\n".join(messages_to_send)
                    for chunk in [full_message[i:i + 1900] for i in range(0, len(full_message), 1900)]:
                        await channel.send(f"```\n{chunk}\n```")
                except discord.HTTPException as e:
                    print(f"Failed to send log to Discord (HTTPException): {e}")
                    logging.error(f"Failed to send log to Discord (HTTPException): {e}")
                except Exception as e:
                    print(f"Failed to send log to Discord (General Error): {e}")
                    logging.error(f"Failed to send log to Discord (General Error): {e}")
            else:
                print(f"Discord log channel with ID {self.log_channel_id} not found.")
