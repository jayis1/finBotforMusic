import asyncio
import discord
from discord.ext import commands
from googleapiclient.discovery import build
import random
import logging
import time
import os
import shutil

import config

from .youtube import YTDLSource, FFMPEG_OPTIONS, YTDL_FORMAT_OPTIONS
from .queuebuffer import QueueBuffer

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.song_queues = {}
        self.search_results = {}
        self.current_song = {}
        self.nowplaying_message = {}
        self.queue_message = {}
        self.playback_speed = {}
        self.youtube_speeds = [0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0]
        self.looping = {}
        self.song_start_time = {}
        self.nowplaying_tasks = {}
        self.current_volume = {}
        self.inactivity_timers = {}

    async def get_queue(self, guild_id):
        if guild_id not in self.song_queues:
            self.song_queues[guild_id] = asyncio.Queue()
        return self.song_queues[guild_id]

    def create_embed(self, title, description, color=discord.Color.blurple(), **kwargs):
        embed = discord.Embed(title=title, description=description, color=color)
        for key, value in kwargs.items():
            embed.add_field(name=key, value=value, inline=False)
        return embed

    def _get_progress_bar(self, current_time, total_duration, bar_length=20):
        if total_duration == 0:
            return "━━━━━━━━━━━━"  # Default empty bar

        progress = (current_time / total_duration)
        filled_length = int(bar_length * progress)
        bar = "━" * filled_length + "●" + "━" * (bar_length - filled_length - 1)
        return bar

    async def _disconnect_if_idle(self, guild_id):
        if guild_id in self.inactivity_timers:
            del self.inactivity_timers[guild_id]
        guild = self.bot.get_guild(guild_id)
        if guild and guild.voice_client and not guild.voice_client.is_playing():
            await guild.voice_client.disconnect()
            logging.info(f"Bot disconnected from voice channel in {guild.name} due to inactivity.")

    def _start_inactivity_timer(self, guild_id):
        if guild_id in self.inactivity_timers:
            self.inactivity_timers[guild_id].cancel()
        self.inactivity_timers[guild_id] = self.bot.loop.call_later(600, lambda: asyncio.ensure_future(self._disconnect_if_idle(guild_id)))

    @commands.command(name="join")
    async def join(self, ctx):
        logging.info(f"Join command invoked by {ctx.author} in {ctx.guild.name}")
        if not ctx.author.voice:
            logging.warning(f"User {ctx.author} not in a voice channel when trying to join.")
            return await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} You are not connected to a voice channel.", discord.Color.red()))
        if ctx.voice_client:
            await ctx.voice_client.move_to(ctx.author.voice.channel)
            logging.info(f"Bot moved to voice channel {ctx.author.voice.channel} in {ctx.guild.name}")
        else:
            await ctx.author.voice.channel.connect()
            logging.info(f"Bot joined voice channel {ctx.author.voice.channel} in {ctx.guild.name}")
        await ctx.send(embed=self.create_embed("Joined Channel", f"{config.SUCCESS_EMOJI} Joined `{ctx.author.voice.channel}`"))

    @commands.command(name="leave")
    async def leave(self, ctx):
        logging.info(f"Leave command invoked by {ctx.author} in {ctx.guild.name}")
        if ctx.voice_client:
            await ctx.voice_client.disconnect()
            logging.info(f"Bot disconnected from voice channel in {ctx.guild.name}")
            
            # Cancel nowplaying update task
            if ctx.guild.id in self.nowplaying_tasks and self.nowplaying_tasks[ctx.guild.id] and not self.nowplaying_tasks[ctx.guild.id].done():
                self.nowplaying_tasks[ctx.guild.id].cancel()
                del self.nowplaying_tasks[ctx.guild.id]

            # Clear the yt-dlp cache
            if os.path.exists("yt_dlp_cache"):
                shutil.rmtree("yt_dlp_cache")
                os.makedirs("yt_dlp_cache")
                logging.info("Cleared the yt-dlp cache.")

            await ctx.send(embed=self.create_embed("Left Channel", f"{config.SUCCESS_EMOJI} Successfully disconnected from the voice channel."))
        else:
            logging.warning(f"Leave command invoked but bot not in a voice channel in {ctx.guild.name}")
            await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} I am not currently in a voice channel.", discord.Color.red()))

    @commands.command(name="search")
    async def search(self, ctx, *, query):
        logging.info(f"Search command invoked by {ctx.author} in {ctx.guild.name} with query: {query}")
        if not config.YOUTUBE_API_KEY:
            logging.error("YouTube API key is not set.")
            return await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} YouTube API key is not set.", discord.Color.red()))
        try:
            youtube_service = build("youtube", "v3", developerKey=config.YOUTUBE_API_KEY)
            search_response = youtube_service.search().list(q=query, part="snippet", maxResults=10, type="video").execute()
            
            if not search_response:
                logging.warning(f"YouTube API returned empty response for query: {query}")
                return await ctx.send(embed=self.create_embed("Search Error", "The YouTube API returned an empty response. Please check your API key.", discord.Color.red()))

            videos = [(item["snippet"]["title"], item["id"]["videoId"]) for item in search_response.get("items", [])]
            if not videos:
                logging.info(f"No videos found for query: {query}")
                return await ctx.send(embed=self.create_embed("No Results", f"{config.ERROR_EMOJI} No songs found for your query.", discord.Color.orange()))
            self.search_results[ctx.guild.id] = videos
            response = "\n".join(f"**{i+1}.** {title}" for i, (title, _) in enumerate(videos))
            logging.info(f"Found {len(videos)} search results for query: {query}")
            await ctx.send(embed=self.create_embed("Search Results", response))
        except Exception as e:
            logging.error(f"Error in search command for query '{query}': {e}")
            await ctx.send(embed=self.create_embed("Search Error", f"An error occurred: {e}", discord.Color.red()))

    @commands.command(name="play")
    async def play(self, ctx, *, query):
        logging.info(f"--- Play command initiated by {ctx.author} ---")
        
        # 1. Acknowledge and ensure bot is in a voice channel
        await ctx.send(embed=self.create_embed("Processing", f"{config.QUEUE_EMOJI} Fetching your request..."))
        
        if not ctx.author.voice:
            logging.warning("User not in a voice channel.")
            return await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} You must be in a voice channel to play music.", discord.Color.red()))

        if not ctx.voice_client:
            logging.info("Bot not in a voice channel, attempting to join.")
            await ctx.author.voice.channel.connect()
        
        logging.info(f"Bot is in voice channel: {ctx.voice_client.channel}")
        
        queue = await self.get_queue(ctx.guild.id)
        
        try:
            # 2. Determine URL and playlist status
            if query.isdigit() and ctx.guild.id in self.search_results:
                url = f"https://www.youtube.com/watch?v={self.search_results[ctx.guild.id][int(query) - 1][1]}"
            else:
                url = query

            ytdl_opts = YTDL_FORMAT_OPTIONS.copy()
            is_playlist = 'list=' in url or 'playlist' in url or 'start_radio' in url
            ytdl_opts['noplaylist'] = not is_playlist
            logging.info(f"Processing URL: {url} (Is Playlist: {is_playlist})")

            # 3. Fetch songs in a non-blocking way
            songs, errors = await YTDLSource.from_url(url, loop=self.bot.loop, ytdl_opts=ytdl_opts)
            logging.info(f"Fetched {len(songs)} songs with {len(errors)} errors.")

            if not songs:
                return await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} Could not fetch any songs. Please check the URL or search query.", discord.Color.red()))

            # 4. Buffer and queue songs
            buffer = QueueBuffer()
            playable_songs, unplayable_songs = buffer.test_playlist(songs)
            logging.info(f"Found {len(playable_songs)} playable and {len(unplayable_songs)} unplayable songs.")

            if not playable_songs:
                return await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} No playable songs found.", discord.Color.red()))

            for song in playable_songs:
                await queue.put(song)
            
            # 5. Send confirmation messages
            if len(playable_songs) > 1:
                await ctx.send(embed=self.create_embed("Playlist Added", f"{config.SUCCESS_EMOJI} Added {len(playable_songs)} songs to the queue."))
            else:
                await ctx.send(embed=self.create_embed("Song Added", f"{config.QUEUE_EMOJI} Added `{playable_songs[0].title}` to the queue."))

            if unplayable_songs:
                unplayable_titles = [s.title for s in unplayable_songs if s.title]
                await ctx.send(embed=self.create_embed("Unplayable Songs", f"{config.ERROR_EMOJI} Skipped {len(unplayable_songs)} unplayable songs:\n- " + "\n- ".join(unplayable_titles), discord.Color.orange()))
            
            if errors:
                error_message = "\n".join([f"- {e}" for e in errors])
                await ctx.send(embed=self.create_embed("Playlist Errors", f"{config.ERROR_EMOJI} Some songs could not be loaded:\n```\n{error_message}\n```", discord.Color.red()))

        except Exception as e:
            logging.error(f"Error in play command: {e}", exc_info=True)
            await ctx.send(embed=self.create_embed("Error", f"An unexpected error occurred: {e}", discord.Color.red()))

        # 6. Start playback
        if not ctx.voice_client.is_playing() and not queue.empty():
            logging.info("Voice client is not playing and queue is not empty. Calling play_next.")
            await self.play_next(ctx)
        else:
            logging.info("Voice client is already playing or queue is empty.")

    async def play_next(self, ctx):
        logging.info("play_next called.")
        if ctx.voice_client.is_playing():
            logging.warning("play_next called but audio is already playing.")
            return
            
        queue = await self.get_queue(ctx.guild.id)
        if not queue.empty() and ctx.voice_client:
            data = await queue.get()
            
            try:
                logging.info(f"Attempting to play {data.title}")
                
                player = discord.FFmpegPCMAudio(data.url, **FFMPEG_OPTIONS)
                ctx.voice_client.play(player, after=lambda e: self.bot.loop.create_task(self._after_playback(ctx, e)))

                self.current_song[ctx.guild.id] = data
                self.song_start_time[ctx.guild.id] = time.time()
                await self.bot.change_presence(activity=discord.Activity(type=discord.ActivityType.listening, name=data.title))
                logging.info(f"Playing {data.title} in {ctx.guild.name}")
                
                if ctx.guild.id not in self.nowplaying_tasks or self.nowplaying_tasks[ctx.guild.id].done():
                    self.nowplaying_tasks[ctx.guild.id] = self.bot.loop.create_task(self._update_nowplaying_message(ctx.guild.id, ctx.channel.id))
            except Exception as e:
                logging.error(f"Error playing next song: {e}", exc_info=True)
                await ctx.send(embed=self.create_embed("Error", f"Could not play the next song: {e}", discord.Color.red()))
        else:
            logging.info("Queue is empty, stopping playback.")
            await self.bot.change_presence(activity=None)
            self._start_inactivity_timer(ctx.guild.id)

    async def _update_nowplaying_message(self, guild_id, channel_id):
        logging.info(f"_update_nowplaying_message: Starting task for guild {guild_id}")
        while True:
            try:
                guild = self.bot.get_guild(guild_id)
                if not guild or not guild.voice_client:
                    logging.warning(f"_update_nowplaying_message: Bot not in a voice channel for guild {guild_id}. Cancelling task.")
                    break

                channel = self.bot.get_channel(channel_id)
                if not channel:
                    logging.warning(f"_update_nowplaying_message: Channel ({channel_id}) not found. Cancelling task.")
                    break
                
                await self._update_nowplaying_display(guild_id, channel.id, silent_update=True)
                logging.debug(f"_update_nowplaying_message: Message updated for guild {guild_id}. Stored Message ID: {self.nowplaying_message.get(guild_id).id if self.nowplaying_message.get(guild_id) else 'None'}")
                await asyncio.sleep(30)  # Update every 30 seconds
            except asyncio.CancelledError:
                logging.info(f"_update_nowplaying_message: Task cancelled for {guild_id}")
                break
            except Exception as e:
                logging.error(f"_update_nowplaying_message: Error updating message for guild {guild_id}: {e}", exc_info=True)
                await asyncio.sleep(5) # Wait before retrying

    async def _update_nowplaying_display(self, guild_id, channel_id, silent_update=False):
        logging.debug(f"_update_nowplaying_display: Called for guild {guild_id}, channel {channel_id}. Silent: {silent_update}.")
        guild = self.bot.get_guild(guild_id)
        channel = self.bot.get_channel(channel_id)

        if not guild or not channel:
            logging.warning(f"nowplaying_display: Guild ({guild_id}) or channel ({channel_id}) not found. Aborting update.")
            return

        current_nowplaying_message = self.nowplaying_message.get(guild_id)
        logging.debug(f"_update_nowplaying_display: Stored message object: {current_nowplaying_message.id if current_nowplaying_message else 'None'}")

        if guild_id in self.current_song and self.current_song[guild_id]:
            data = self.current_song[guild_id]
            queue = await self.get_queue(guild_id)
            
            current_time = int(time.time() - self.song_start_time[guild_id])
            progress_bar = self._get_progress_bar(current_time, data.duration)
            
            queue_list = list(queue._queue)
            total_duration = sum(item.duration for item in queue_list)
            
            embed = self.create_embed(f"{config.PLAY_EMOJI} Now Playing", 
                                      f"[{data.title}]({data.webpage_url})\n\n{progress_bar} {current_time // 60}:{current_time % 60:02d} / {data.duration // 60}:{data.duration % 60:02d}")
            embed.add_field(name="Queue", value=f"{len(queue_list)} songs remaining")
            embed.set_footer(text=f"Total Queue Duration: {total_duration // 60}:{total_duration % 60:02d}")
            embed.set_thumbnail(url=data.thumbnail)
            
            view = discord.ui.View(timeout=None)
            view.add_item(discord.ui.Button(emoji=config.PLAY_EMOJI, style=discord.ButtonStyle.secondary, custom_id="play"))
            view.add_item(discord.ui.Button(emoji=config.PAUSE_EMOJI, style=discord.ButtonStyle.secondary, custom_id="pause"))
            view.add_item(discord.ui.Button(emoji=config.SKIP_EMOJI, style=discord.ButtonStyle.secondary, custom_id="skip"))
            view.add_item(discord.ui.Button(emoji=config.ERROR_EMOJI, style=discord.ButtonStyle.danger, custom_id="stop"))
            view.add_item(discord.ui.Button(emoji=config.QUEUE_EMOJI, style=discord.ButtonStyle.primary, custom_id="queue"))

            if current_nowplaying_message:
                try:
                    # Attempt to fetch the message to ensure it still exists and is valid
                    fetched_message = await channel.fetch_message(current_nowplaying_message.id)
                    logging.debug(f"nowplaying_display: Fetched message {fetched_message.id} for editing.")
                    await fetched_message.edit(embed=embed, view=view)
                    self.nowplaying_message[guild_id] = fetched_message # Update reference in case it changed
                    logging.info(f"nowplaying_display: Edited message {fetched_message.id} for {data.title} in {guild.name}")
                except discord.NotFound:
                    logging.warning(f"nowplaying_display: Previous message {current_nowplaying_message.id} not found for editing in {guild.name}. Sending new message.")
                    self.nowplaying_message[guild_id] = await channel.send(embed=embed, view=view)
                    logging.info(f"nowplaying_display: Sent new message {self.nowplaying_message[guild_id].id} for {data.title} in {guild.name}")
                except Exception as e:
                    logging.error(f"nowplaying_display: Error editing message {current_nowplaying_message.id} for {data.title} in {guild.name}: {e}", exc_info=True)
                    # If editing fails for other reasons, try sending a new message
                    self.nowplaying_message[guild_id] = await channel.send(embed=embed, view=view)
                    logging.info(f"nowplaying_display: Sent new message {self.nowplaying_message[guild_id].id} after edit failure for {data.title} in {guild.name}")
            else:
                self.nowplaying_message[guild_id] = await channel.send(embed=embed, view=view)
                logging.info(f"nowplaying_display: Sent initial message {self.nowplaying_message[guild_id].id} for {data.title} in {guild.name}")
        else: # Nothing is playing
            logging.debug(f"nowplaying_display: Nothing playing for guild {guild_id}. Stored message: {current_nowplaying_message.id if current_nowplaying_message else 'None'}")
            if current_nowplaying_message:
                try:
                    # Attempt to fetch before deleting to avoid NotFound error if already gone
                    fetched_message = await channel.fetch_message(current_nowplaying_message.id)
                    logging.debug(f"nowplaying_display: Fetched message {fetched_message.id} for deletion.")
                    await fetched_message.delete()
                    del self.nowplaying_message[guild_id]
                    logging.info(f"nowplaying_display: Deleted previous message {current_nowplaying_message.id} as nothing is playing in {guild.name}")
                except discord.NotFound:
                    logging.warning(f"nowplaying_display: Previous message {current_nowplaying_message.id} not found for deletion in {guild.name}. Already gone?")
                    pass # Message already deleted
                except Exception as e:
                    logging.error(f"nowplaying_display: Error deleting message {current_nowplaying_message.id} in {guild.name}: {e}", exc_info=True)
            
            # Only send "Not Playing" if not a silent update and no message is currently displayed
            if not silent_update and not current_nowplaying_message:
                self.nowplaying_message[guild_id] = await channel.send(embed=self.create_embed("Not Playing", "The bot is not currently playing anything."))
                logging.info(f"nowplaying_display: Nothing playing in {guild.name}. Sent 'Not Playing' message.")
            elif silent_update and current_nowplaying_message and current_nowplaying_message.embeds and current_nowplaying_message.embeds[0].title == "Not Playing":
                # If it's a silent update and the current message is "Not Playing", do nothing to avoid spam
                logging.debug(f"nowplaying_display: Silent update, and 'Not Playing' message already present for {guild.name}. Skipping.")
                pass
            elif silent_update and not current_nowplaying_message:
                # If it's a silent update and no message is present, do nothing. A new message will be sent when a song starts.
                logging.debug(f"nowplaying_display: Silent update, no message present for {guild.name}. Skipping sending 'Not Playing'.")
                pass
            else:
                # If it's not a silent update, or if there's an old song message, send a new "Not Playing" message
                if not silent_update:
                    self.nowplaying_message[guild_id] = await channel.send(embed=self.create_embed("Not Playing", "The bot is not currently playing anything."))
                    logging.info(f"nowplaying_display: Nothing playing in {guild.name}. Sent 'Not Playing' message (non-silent or old message).")

    async def _after_playback(self, ctx, error):
        queue = await self.get_queue(ctx.guild.id)
        if error:
            logging.error(f"Player error in {ctx.guild.name}: {error}", exc_info=True)
            # Optionally, send an error message to the channel
            # await ctx.send(embed=self.create_embed("Playback Error", f"An error occurred during playback: {error}", discord.Color.red()))
        
        # Check if looping is enabled
        if self.looping.get(ctx.guild.id):
            # If looping, re-add the current song to the queue
            current_song_data = self.current_song.get(ctx.guild.id)
            if current_song_data:
                await queue.put(current_song_data)
                logging.info(f"Looping enabled. Re-added {current_song_data.title} to queue.")
        
        # Play the next song in the queue
        await self.play_next(ctx)

        # If queue is empty and not looping, cancel the nowplaying update task
        if queue.empty() and not self.looping.get(ctx.guild.id):
            if ctx.guild.id in self.nowplaying_tasks and self.nowplaying_tasks[ctx.guild.id] and not self.nowplaying_tasks[ctx.guild.id].done():
                self.nowplaying_tasks[ctx.guild.id].cancel()
                del self.nowplaying_tasks[ctx.guild.id]

    @commands.command(name="volume")
    async def volume(self, ctx, volume: int):
        logging.info(f"Volume command invoked by {ctx.author} in {ctx.guild.name} with volume: {volume}")
        guild_id = ctx.guild.id
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} Not currently playing anything to set volume for.", discord.Color.red()))
            return

        if 0 <= volume <= 200:
            new_volume_float = volume / 100
            ctx.voice_client.source.volume = new_volume_float
            self.current_volume[guild_id] = new_volume_float # Store the volume
            logging.info(f"Volume set to {volume}% in {ctx.guild.name}. Actual source volume: {ctx.voice_client.source.volume}")
            await ctx.send(embed=self.create_embed("Volume Control", f"{config.SUCCESS_EMOJI} Volume set to {volume}%"))
        else:
            logging.warning(f"Invalid volume {volume} provided by {ctx.author} in {ctx.guild.name}")
            await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} Volume must be between 0 and 200.", discord.Color.red()))

    @commands.command(name="nowplaying")
    async def nowplaying(self, ctx, silent=False):
        logging.info(f"Nowplaying command invoked by {ctx.author} in {ctx.guild.name} (silent: {silent})")
        guild_id = ctx.guild.id

        # If invoked by a user, send a new message and store it for future updates
        if not silent:
            # Delete previous nowplaying message if it exists
            if guild_id in self.nowplaying_message and self.nowplaying_message[guild_id]:
                try:
                    await self.nowplaying_message[guild_id].delete()
                    del self.nowplaying_message[guild_id]
                    logging.info(f"nowplaying: Deleted previous nowplaying message for {ctx.guild.name}")
                except discord.NotFound:
                    pass
                except Exception as e:
                    logging.error(f"nowplaying: Error deleting old message in {ctx.guild.name}: {e}", exc_info=True)

            # Send a new message and store it
            if guild_id in self.current_song and self.current_song[guild_id]:
                data = self.current_song[guild_id]
                queue = await self.get_queue(ctx.guild.id)
                current_time = int(time.time() - self.song_start_time[guild_id])
                progress_bar = self._get_progress_bar(current_time, data.duration)

                queue_list = list(queue._queue)
                total_duration = sum(item.duration for item in queue_list)

                embed = self.create_embed(f"{config.PLAY_EMOJI} Now Playing", 
                                          f"[{data.title}]({data.webpage_url})\n\n{progress_bar} {current_time // 60}:{current_time % 60:02d} / {data.duration // 60}:{data.duration % 60:02d}")
                embed.add_field(name="Queue", value=f"{len(queue_list)} songs remaining")
                embed.set_footer(text=f"Total Queue Duration: {total_duration // 60}:{total_duration % 60:02d}")
                embed.set_thumbnail(url=data.thumbnail)
                
                view = discord.ui.View(timeout=None)
                view.add_item(discord.ui.Button(emoji=config.PLAY_EMOJI, style=discord.ButtonStyle.secondary, custom_id="play"))
                view.add_item(discord.ui.Button(emoji=config.PAUSE_EMOJI, style=discord.ButtonStyle.secondary, custom_id="pause"))
                view.add_item(discord.ui.Button(emoji=config.SKIP_EMOJI, style=discord.ButtonStyle.secondary, custom_id="skip"))
                view.add_item(discord.ui.Button(emoji=config.ERROR_EMOJI, style=discord.ButtonStyle.danger, custom_id="stop"))
                view.add_item(discord.ui.Button(emoji=config.QUEUE_EMOJI, style=discord.ButtonStyle.primary, custom_id="queue"))
                
                self.nowplaying_message[guild_id] = await ctx.send(embed=embed, view=view)
                logging.info(f"nowplaying: Sent initial message {self.nowplaying_message[guild_id].id} for {data.title} in {ctx.guild.name}")
            else:
                self.nowplaying_message[guild_id] = await ctx.send(embed=self.create_embed("Not Playing", "The bot is not currently playing anything."))
                logging.info(f"nowplaying: Sent initial 'Not Playing' message for {ctx.guild.name}")
        
        # The background task will call _update_nowplaying_display silently
        # This command itself doesn't need to call it if it just sent a new message
        # If it was a silent call (from the background task), then _update_nowplaying_display is already called by the task loop

    @commands.command(name="queue")
    async def queue_info(self, ctx):
        logging.info(f"Queue command invoked by {ctx.author} in {ctx.guild.name})")
        queue = await self.get_queue(ctx.guild.id)
        if not queue.empty():
            queue_list = list(queue._queue)
            total_duration = sum(item.duration for item in queue_list)
            
            queue_text = ""
            for i, item in enumerate(queue_list):
                queue_text += f"**{i+1}.** {item.title} `({item.duration // 60}:{item.duration % 60:02d})`\n"

            embed = self.create_embed(f"{config.QUEUE_EMOJI} Current Queue", queue_text)
            embed.set_footer(text=f"Total Duration: {total_duration // 60}:{total_duration % 60:02d}")
            
            logging.info(f"Displaying queue with {len(queue_list)} songs for {ctx.guild.name})")
            await ctx.send(embed=embed)
        else:
            logging.info(f"Queue is empty for {ctx.guild.name})")
            await ctx.send(embed=self.create_embed("Empty Queue", "The queue is currently empty."))

    @commands.command(name="skip")
    async def skip(self, ctx):
        logging.info(f"Skip command invoked by {ctx.author} in {ctx.guild.name}")
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.stop()
            logging.info(f"Song skipped in {ctx.guild.name}")
            await ctx.send(embed=self.create_embed("Song Skipped", f"{config.SKIP_EMOJI} The current song has been skipped."))
        else:
            logging.warning(f"Skip command invoked but nothing is playing in {ctx.guild.name}")
            await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} No song is currently playing to skip.", discord.Color.red()))

    @commands.command(name="stop")
    async def stop(self, ctx):
        logging.info(f"Stop command invoked by {ctx.author} in {ctx.guild.name}")
        queue = await self.get_queue(ctx.guild.id)
        if not queue.empty():
            while not queue.empty():
                await queue.get()
            logging.info(f"Queue cleared in {ctx.guild.name}")
        if ctx.voice_client:
            ctx.voice_client.stop()
            logging.info(f"Voice client stopped in {ctx.guild.name}")
        
        # Cancel nowplaying update task
        if ctx.guild.id in self.nowplaying_tasks and self.nowplaying_tasks[ctx.guild.id] and not self.nowplaying_tasks[ctx.guild.id].done():
            self.nowplaying_tasks[ctx.guild.id].cancel()
            del self.nowplaying_tasks[ctx.guild.id]

        await self.bot.change_presence(activity=None)
        await ctx.send(embed=self.create_embed("Playback Stopped", f"{config.SUCCESS_EMOJI} Music has been stopped and the queue has been cleared."))

    @commands.command(name="pause")
    async def pause(self, ctx):
        logging.info(f"Pause command invoked by {ctx.author} in {ctx.guild.name}")
        if ctx.voice_client and ctx.voice_client.is_playing():
            ctx.voice_client.pause()
            logging.info(f"Music paused in {ctx.guild.name}")
            await ctx.send(embed=self.create_embed("Playback Paused", f"{config.PAUSE_EMOJI} The music has been paused."))
        else:
            logging.warning(f"Pause command invoked but nothing is playing or already paused in {ctx.guild.name}")
            await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} No music is currently playing to pause.", discord.Color.red()))

    @commands.command(name="resume")
    async def resume(self, ctx):
        logging.info(f"Resume command invoked by {ctx.author} in {ctx.guild.name}")
        if ctx.voice_client and ctx.voice_client.is_paused():
            ctx.voice_client.resume()
            logging.info(f"Music resumed in {ctx.guild.name}")
            await ctx.send(embed=self.create_embed("Playback Resumed", f"{config.PLAY_EMOJI} The music has been resumed."))
        else:
            logging.warning(f"Resume command invoked but nothing is paused or playing in {ctx.guild.name}")
            await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} No music is currently paused to resume.", discord.Color.red()))

    @commands.command(name="clear")
    async def clear(self, ctx):
        logging.info(f"Clear command invoked by {ctx.author} in {ctx.guild.name}")
        queue = await self.get_queue(ctx.guild.id)
        if not queue.empty():
            while not queue.empty():
                await queue.get()
            logging.info(f"Queue cleared by {ctx.author} in {ctx.guild.name}")
            await ctx.send(embed=self.create_embed("Queue Cleared", f"{config.SUCCESS_EMOJI} The queue has been cleared."))
        else:
            logging.info(f"Clear command invoked but queue already empty in {ctx.guild.name}")
            await ctx.send(embed=self.create_embed("Empty Queue", "The queue is already empty."))

    

    @commands.command(name="remove")
    async def remove(self, ctx, number: int):
        logging.info(f"Remove command invoked by {ctx.author} in {ctx.guild.name} to remove song number {number}")
        queue = await self.get_queue(ctx.guild.id)
        if number > 0 and number <= queue.qsize():
            removed_song = None
            temp_queue = asyncio.Queue()
            for i in range(queue.qsize()):
                song = await queue.get()
                if i + 1 == number:
                    removed_song = song
                else:
                    await temp_queue.put(song)
            
            self.song_queues[ctx.guild.id] = temp_queue
            
            if removed_song:
                logging.info(f"Removed song '{removed_song.title}' (number {number}) from queue in {ctx.guild.name}")
                await ctx.send(embed=self.create_embed("Song Removed", f"{config.SUCCESS_EMOJI} Removed `{removed_song.title}` from the queue."))
            else:
                logging.error(f"Failed to remove song at position {number} from queue in {ctx.guild.name}")
                await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} Could not find a song at that position.", discord.Color.red()))
        else:
            logging.warning(f"Invalid song number {number} provided by {ctx.author} for remove command in {ctx.guild.name}")
            await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} Invalid song number.", discord.Color.red()))

    @commands.command(name="loop")
    async def loop(self, ctx):
        logging.info(f"Loop command invoked by {ctx.author} in {ctx.guild.name}")
        guild_id = ctx.guild.id
        self.looping[guild_id] = not self.looping.get(guild_id, False)
        status = "enabled" if self.looping[guild_id] else "disabled"
        logging.info(f"Looping {status} for {ctx.guild.name}")
        await ctx.send(embed=self.create_embed("Loop Toggled", f"{config.SUCCESS_EMOJI} Looping is now **{status}**."))

    def _get_current_speed_index(self, guild_id):
        current_speed = self.playback_speed.get(guild_id, 1.0)
        try:
            return self.youtube_speeds.index(current_speed)
        except ValueError:
            return self.youtube_speeds.index(1.0) # Default to 1.0 if current speed not in list

    async def _set_speed(self, ctx, new_speed):
        guild_id = ctx.guild.id
        if not ctx.voice_client or not ctx.voice_client.is_playing():
            await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} No song is currently playing to change speed.", discord.Color.red()))
            return

        self.playback_speed[guild_id] = new_speed
        logging.info(f"Setting playback speed to {new_speed} for {ctx.guild.name}")

        # Re-create the player with the new speed
        current_song_data = self.current_song.get(guild_id)
        if current_song_data:
            # Stop current playback
            ctx.voice_client.stop()

            # Dynamically create FFMPEG options with atempo filter
            player_options = FFMPEG_OPTIONS.copy()
            if new_speed != 1.0:
                player_options['options'] += f' -filter:a "atempo={new_speed}"'

            # Create and play the new player with the updated speed
            player = discord.FFmpegOpusAudio(current_song_data.url, **player_options)
            player.volume = self.current_volume.get(guild_id, 1.0) # Apply stored volume
            ctx.voice_client.play(player, after=lambda e: self.bot.loop.create_task(self._after_playback(ctx, e)))
            
            self.song_start_time[guild_id] = time.time() # Reset start time for accurate progress bar
            await ctx.send(embed=self.create_embed("Speed Changed", f"{config.SUCCESS_EMOJI} Playback speed set to **{new_speed}x**."))
            await self.nowplaying(ctx, silent=True) # Update nowplaying message immediately
        else:
            await ctx.send(embed=self.create_embed("Error", f"{config.ERROR_EMOJI} Could not apply speed change. No current song data.", discord.Color.red()))

    @commands.command(name="speedhigher")
    async def speedhigher(self, ctx):
        logging.info(f"Speedhigher command invoked by {ctx.author} in {ctx.guild.name}")
        guild_id = ctx.guild.id
        current_index = self._get_current_speed_index(guild_id)
        if current_index < len(self.youtube_speeds) - 1:
            new_speed = self.youtube_speeds[current_index + 1]
            await self._set_speed(ctx, new_speed)
        else:
            await ctx.send(embed=self.create_embed("Speed Limit", f"{config.ERROR_EMOJI} Already at maximum speed ({self.youtube_speeds[-1]}x).", discord.Color.orange()))

    @commands.command(name="speedlower")
    async def speedlower(self, ctx):
        logging.info(f"Speedlower command invoked by {ctx.author} in {ctx.guild.name}")
        guild_id = ctx.guild.id
        current_index = self._get_current_speed_index(guild_id)
        if current_index > 0:
            new_speed = self.youtube_speeds[current_index - 1]
            await self._set_speed(ctx, new_speed)
        else:
            await ctx.send(embed=self.create_embed("Speed Limit", f"{config.ERROR_EMOJI} Already at minimum speed ({self.youtube_speeds[0]}x).", discord.Color.orange()))

    @commands.command(name="shuffle")
    async def shuffle(self, ctx):
        logging.info(f"Shuffle command invoked by {ctx.author} in {ctx.guild.name}")
        queue = await self.get_queue(ctx.guild.id)
        if queue.empty():
            await ctx.send(embed=self.create_embed("Empty Queue", f"{config.ERROR_EMOJI} The queue is empty, nothing to shuffle.", discord.Color.orange()))
            return

        # Get all items from the queue
        queue_list = []
        while not queue.empty():
            queue_list.append(await queue.get())

        # Shuffle the list
        random.shuffle(queue_list)

        # Put items back into the queue
        for item in queue_list:
            await queue.put(item)
        
        logging.info(f"Queue shuffled for {ctx.guild.name}")
        await ctx.send(embed=self.create_embed("Queue Shuffled", f"{config.SUCCESS_EMOJI} The queue has been shuffled."))

    @commands.Cog.listener()
    async def on_interaction(self, interaction):
        if interaction.type == discord.InteractionType.component:
            custom_id = interaction.data["custom_id"]
            logging.info(f"Interaction received: {custom_id} by {interaction.user} in {interaction.guild.name}")
            ctx = await self.bot.get_context(interaction.message)
            if custom_id == "play":
                await self.resume(ctx)
            elif custom_id == "pause":
                await self.pause(ctx)
            elif custom_id == "resume":
                await self.resume(ctx)
            elif custom_id == "skip":
                await self.skip(ctx)
            elif custom_id == "stop":
                await self.stop(ctx)
            elif custom_id == "queue":
                queue = await self.get_queue(ctx.guild.id)
                if not queue.empty():
                    queue_list = "\n".join(f"**{i+1}.** {item.title}" for i, item in enumerate(list(queue._queue)))
                    embed = self.create_embed(f"{config.QUEUE_EMOJI} Current Queue", queue_list)
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                else:
                    embed = self.create_embed("Empty Queue", "The queue is currently empty.")
                    await interaction.response.send_message(embed=embed, ephemeral=True)
                return  # Exit early as we've already responded
            await interaction.response.defer()

async def setup(bot):
    try:
        await bot.add_cog(Music(bot))
    except Exception as e:
        logging.error(f"Failed to load music cog: {e}", exc_info=True)