import asyncio

class QueueBuffer:
    def __init__(self):
        self.buffer = asyncio.Queue()

    async def add_to_buffer(self, item):
        await self.buffer.put(item)

    async def get_from_buffer(self):
        return await self.buffer.get()

    def is_empty(self):
        return self.buffer.empty()

    def test_playlist(self, songs):
        playable_songs = []
        unplayable_songs = []
        for song in songs:
            if song.url:
                playable_songs.append(song)
            else:
                unplayable_songs.append(song)
        return playable_songs, unplayable_songs

async def setup(bot):
    pass
