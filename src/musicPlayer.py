import yt_dlp as youtube_dl
import discord
from discord.ext import commands
#import asyncio


class Song():
    def __init__(self, title: str = None, artist: str = None):
        self.title: str = title
        self.artist: str = artist
        self.url: str = None
        self.ytdl_opts = {
        'format': 'bestaudio/best',         # Get the best audio quality
        'extractaudio': True,               # Extract audio only
        'audioformat': 'mp3',               # Convert to MP3 format
        'noplaylist': True,                 # Don't download playlists
        'quiet': True,                      # Show progress
        'postprocessors': [{                # Post-process audio to convert to MP3
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',      # Audio quality (bitrate)
        }],
        'default_search': 'ytsearch1',       # Limit search to the first result
        'quiet': True,                       # Suppress console output for faster processing
        'no_warnings': True,                 # Suppress warnings
        }

    def downloadTrack(self) -> bool:
        searchName = self.artist + ' ' + self.title
        with youtube_dl.YoutubeDL(self.ytdl_opts) as ytdl:
            trackInfo = ytdl.extract_info(searchName, download=False)
        if trackInfo is not None:
            self.url = trackInfo['entries'][0]['url']
            return True
        else: return False



class SongQueue():
    def __init__(self):
        self.__queue: list[Song] = []         # FIFO queue
        self.isPlaying = False
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
    def __init__(self):
        self.queue: SongQueue = SongQueue()
        self.voiceClient: discord.VoiceClient = None


    def playNext(self):
        if self.voiceClient is not None:
            # Bot is in channel
            if self.queue.length > 0:
                self.__play()
            else:
                print("Song queue is empty")
        print("working on it...")


    def __play(self):
        self.queue.isPlaying = True
        if self.voiceClient is not None:
            currentTrack = self.queue.pop()
            self.voiceClient.play(source=discord.FFmpegPCMAudio(currentTrack.url), after=lambda e: self.playNext())
        else:
            print("Voice client is null")


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
        if self.voiceClient.is_playing():
            self.queue.addSong(track=track, requestor=interaction.user.id)
            return "Added to queue"
        else:
            self.queue.addSong(track=track, requestor=interaction.user.id)
            connected = await self.join(interaction=interaction)
            if connected:
                self.__play()
                return "Playing song"
            else:
                return "Could not connect to voice"

        
