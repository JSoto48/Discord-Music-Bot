import yt_dlp as youtube_dl
import discord
from discord.ext import commands


class Song():
    def __init__(self, title: str = None, artist: str = None):
        self.title: str = title
        self.artist: str = artist
        self.trackUrl: str = None
        self.thumbnailURL: str = None

        self.ytdl_opts = {
            'format': 'bestaudio/best',         # Get the best audio quality
            'noplaylist': True,                 # Don't download playlists
            'quiet': True,                      # Show progress
            'default_search': 'ytsearch1',       # Limit search to the first result
            'no_warnings': True,                 # Suppress warnings
        }


    def getTrackUrl(self) -> bool:
        searchName = self.artist + ' ' + self.title + ' audio'

        with youtube_dl.YoutubeDL(self.ytdl_opts) as ytdl:
            trackInfo = ytdl.extract_info(searchName, download=False)
        if trackInfo is not None:
            self.trackUrl = trackInfo['entries'][0]['url']
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


    def initSong(self, title: str, artist: str) -> Song:
        newSong: Song = Song(title, artist)
        newSong.getTrackUrl()
        apiCall = self.spotifyAPI.search(q=title, limit=1, type='track')
        results = apiCall['tracks']['items'][0]
        images = results['album']['images']
        newSong.thumbnailURL = images[len(images)-1]['url']
        return newSong


    def nowPlayingEmbed(self, track: Song) -> discord.Embed:
        embed = discord.Embed(
            title='Now Playing',
            description=track.title,
            colour=discord.Color.fuchsia()
        )
        embed.set_thumbnail(url=track.thumbnailURL)
        return embed

    async def playNext(self, interaction: discord.Interaction):
        if self.voiceClient is not None:
        # Ensure bot is in channel
            if self.queue.length > 0:
            # Ensure there is songs in the queue
                currentTrack = self.queue.pop()
                self.voiceClient.play(
                    source=discord.FFmpegPCMAudio(currentTrack.trackUrl, options=self.FFmpegOptions),
                    after= await self.playNext(interaction))

                await interaction.channel.send(embed=self.nowPlayingEmbed(currentTrack))
            # else:
            #     #await interaction.response.send_message(f'Queue has ended')
        else:
            print('ERROR: Bot not in channel - from play')


    async def addToQueue(self, songName: str, songArtist:str, interaction: discord.Interaction):
        userVoice = interaction.user.voice

        if not userVoice:
        # User not in Voice channnel
            await interaction.followup.send('Join a voice channel to play music')
            return

        newSong = self.initSong(title=songName, artist=songArtist)

        if self.voiceClient is not None:
        # Bot is in voice channel
            if self.voiceClient.is_playing():
                self.queue.addSong(track=newSong, requestor=interaction.user.id)
                await interaction.followup.send(f'Added {newSong.title} to the queue')
            else:   # Bot is either paused or queue has ended
                    # BUG ? Skips the paused song
                self.queue.addSong(track=newSong, requestor=interaction.user.id)
                self.playNext()
        else:
        # Bot not in voice channel
            try:
                self.voiceClient = await userVoice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f'Error connecting to voice channel: {e.message}')
                return
            
            self.queue.addSong(track=newSong, requestor=interaction.user.id)
            await interaction.followup.send(f'Added {newSong.title} to the queue')
            await self.playNext(interaction=interaction)

