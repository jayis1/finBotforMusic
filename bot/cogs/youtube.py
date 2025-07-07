import asyncio
import yt_dlp
import discord
import logging

FFMPEG_OPTIONS = {
    'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5',
    'options': '-vn'
}

# --- YTDL Options ---
YTDL_STREAM_FORMAT_OPTIONS = {
    "format": "bestaudio/best",
    "nocheckcertificate": False,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "cookiefile": "youtube_cookie.txt" if __import__('os').path.exists("youtube_cookie.txt") else None,
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36)"
    },
    "extractor_args": {"youtube": {"player_client": ["web"]}},
}

YTDL_DOWNLOAD_FORMAT_OPTIONS = {
    "format": "bestaudio/best",
    "outtmpl": "audio_cache/%(extractor)s-%(id)s-%(title)s.%(ext)s",
    "restrictfilenames": True,
    "noplaylist": True,
    "nocheckcertificate": False,
    "ignoreerrors": False,
    "logtostderr": False,
    "quiet": True,
    "no_warnings": True,
    "default_search": "ytsearch",
    "source_address": "0.0.0.0",
    "cookiefile": "youtube_cookie.txt" if __import__('os').path.exists("youtube_cookie.txt") else None,
    "http_headers": {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/100.0.4896.88 Safari/537.36)"
    },
    "extractor_args": {"youtube": {"player_client": ["web"]}},
}

class YTDLSource:
    def __init__(self, data):
        self.data = data
        self.title = data.get("title")
        self.url = data.get("filepath") or data.get("url")
        self.duration = data.get("duration")
        self.thumbnail = data.get("thumbnail")
        self.webpage_url = data.get("webpage_url")

    @classmethod
    async def from_url(cls, url, *, loop=None, ytdl_opts=None):
        loop = loop or asyncio.get_event_loop()
        
        try:
            # Try to stream first
            options = ytdl_opts if ytdl_opts is not None else YTDL_STREAM_FORMAT_OPTIONS.copy()
            data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(options).extract_info(url, download=False))
            logging.info(f"YTDLSource.from_url: Streaming successful for {url}")
        except Exception as e:
            logging.warning(f"Streaming failed for {url}: {e}. Falling back to download.")
            # If streaming fails, download the audio
            options = ytdl_opts if ytdl_opts is not None else YTDL_DOWNLOAD_FORMAT_OPTIONS.copy()
            data = await loop.run_in_executor(None, lambda: yt_dlp.YoutubeDL(options).extract_info(url, download=True))
            logging.info(f"YTDLSource.from_url: Download and extraction complete for {url}")

        logging.info(f"YTDLSource.from_url raw yt-dlp data keys: {data.keys() if isinstance(data, dict) else 'N/A'}")
        logging.info(f"YTDLSource.from_url is_playlist: {'entries' in data}")
        if 'entries' in data:
            logging.info(f"YTDLSource.from_url number of entries: {len(data.get('entries', []))}")

        if "entries" in data:
            return [cls(entry) for entry in data["entries"]]
        else:
            return [cls(data)]
