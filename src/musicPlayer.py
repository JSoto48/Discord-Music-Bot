import yt_dlp as youtube_dl
import discord
from discord.ext import commands
#from responses import Responses
import asyncio


class Song():
    def __init__(self, title: str = None, artist: str = None):
        self.title: str = title
        self.artist: str = artist
        self.url: str = None
        self.ytdl_opts = {
            'format': 'bestaudio/best',         # Get the best audio quality
            'noplaylist': True,                 # Don't download playlists
            'quiet': True,                      # Show progress
            'default_search': 'ytsearch1',       # Limit search to the first result
            'no_warnings': True,                 # Suppress warnings
        }

    def getUrl(self) -> bool:
        searchName = self.artist + ' ' + self.title + ' audio'

        with youtube_dl.YoutubeDL(self.ytdl_opts) as ytdl:
            trackInfo = ytdl.extract_info(searchName, download=False)
        if trackInfo is not None:
            self.url = trackInfo['entries'][0]['url']
            return True
        else: return False



class SongQueue():
    def __init__(self):
        self.__queue: list[Song] = []         # FIFO queue
        self.length = 0

    def addSong(self, track: Song, requestor: str = None) -> None:
        # Adds a song to the queue
        #newElement = (track, requestor)
        self.__queue.append(track)
        self.length += 1

    def pop(self) -> Song:
        # Removes and returns song from the first index of the queue
        self.length -= 1
        return self.__queue.pop(0)




class QueueManager():
    def __init__(self, spotifyAPI):
        self.queue: SongQueue = SongQueue()
        self.voiceClient: discord.VoiceClient = None
        self.spotifyAPI = spotifyAPI
        self.FFmpegOptions = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 'options': '-vn'}


    def playNext(self, interaction: discord.Interaction = None):
        if self.voiceClient is not None:
            # Bot is in channel
            if self.queue.length > 0:
                currentTrack = self.queue.pop()
                self.voiceClient.play(source=discord.FFmpegPCMAudio(currentTrack.url, options=self.FFmpegOptions), after=lambda e: self.playNext())
            #else:
                # Play recommended songs


    async def join(self, interaction: discord.Interaction) -> bool:
        userVoice = interaction.user.voice          # User voice channel activity
        botVC = discord.utils.get(interaction.client.voice_clients, guild=interaction.guild)        # Bot voice client activity

        if not userVoice:
            return False
        else:
            if not botVC:
                try:
                    self.voiceClient = await userVoice.channel.connect()
                    if self.voiceClient:
                        return True
                except Exception as e:
                    return False


    async def addToQueue(self, track: Song, interaction: discord.Interaction) -> str:
        if self.voiceClient is not None:
            # Bot is in channel and playing audio
            if self.voiceClient.is_playing():
                # Add to queue
                self.queue.addSong(track=track, requestor=interaction.user.id)
            else:
                # Skip the paused song
                self.queue.addSong(track=track, requestor=interaction.user.id)
                self.playNext()
            return (f'Added {track.title} to queue')
        else:
            self.queue.addSong(track=track, requestor=interaction.user.id)
            connected = await self.join(interaction=interaction)
            if connected:
                self.playNext()
                return (f'Playing {track.title} by {track.artist}')
            else:
                return "Could not connect to voice"
