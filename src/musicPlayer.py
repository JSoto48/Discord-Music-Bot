import yt_dlp as youtube_dl
import discord
from discord.ext import commands


class Song():
    def __init__(self, title: str = None, artist: str = None):
        self.title: str = title
        self.artist: str = artist
        self.url: str = None

    def downloadTrack(self) -> bool:
        ytdl_opts = {
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

        searchName = self.artist + ' ' + self.title
        with youtube_dl.YoutubeDL(ytdl_opts) as ytdl:
            trackInfo = ytdl.extract_info(searchName, download=False)
        if trackInfo is not None:
            self.url = trackInfo['entries'][0]['url']
            return True
        else: return False



class SongQueue():
    def __init__(self):
        self.__queue: list[Song] = []         # FIFO queue
        self.isPlaying = False

    def addSong(self, track: Song) -> None:
        # Adds a song to the queue
        self.__queue.append(track)

    def pop(self) -> Song:
        # Removes and returns song from the first index of the queue
        return self.queue.pop[0]




class QueueManager():
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.searchQueue: SongQueue = SongQueue()
        self.recommendedQueue: SongQueue = SongQueue()
        self.timer = None


    async def play(self, track: Song, interaction: discord.Interaction) -> str:
        response = ''
        userVoice = interaction.user.voice
        botVC = discord.utils.get(interaction.client.voice_clients, guild=interaction.guild)

        if self.searchQueue.isPlaying or self.recommendedQueue.isPlaying:
            response = "Already playing song, added to queue"
            self.searchQueue.addSong(track)
        elif not userVoice:
            response = 'Join a voice channel to play music'
        else:
            response = 'Playing music'
            if not botVC:
                try:
                    voiceClient = await userVoice.channel.connect()
                except Exception as e:
                    print(e)
                    return e
            
            self.searchQueue.addSong(track)
            self.searchQueue.isPlaying = True
            voiceClient.play(discord.FFmpegPCMAudio(track.url))

        return response


    # async def join(self, interaction: discord.Interaction) -> bool:
    #     userVoice = interaction.user.voice
    #     botVC = discord.utils.get(interaction.client.voice_clients, guild=interaction.guild)
    #     if not userVoice:
    #         print('Join a voice channel to play music')
    #         return False
    #     elif botVC:
    #         print('bot alr in vc')
    #         return False
    #     else:
    #         try:
    #             voiceClient = await userVoice.channel.connect()
    #         except Exception as e:
    #             print(e)
    #             return False
        
