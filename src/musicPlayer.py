import os
import yt_dlp
import pylast
import spotipy
import discord
from math import ceil
from random import choice
from random import randint
from asyncio import run_coroutine_threadsafe
from spotipy.oauth2 import SpotifyClientCredentials

class Song():
    def __init__(self, id: str, title: str, artists: list, requestor: discord.User,
    duration: float = None, thumbnailUrl: str = None):
        self.id: str = id
        self.title: str = title
        self.artists: list = artists                    # Primary artist always at index 0
        self.requestor: discord.User = requestor
        self.duration: float = duration                 # TODO: Extract duration from yt download, currently in ms from spotify
        self.thumbnailUrl: str = thumbnailUrl
        self.__filePath: str = None
    
    def deleteFile(self):
        if self.__filePath is None:
            return
        elif os.path.exists(self.__filePath):
            os.remove(self.__filePath)
            self.__filePath = None

    def getFilePath(self, folderPath: str) -> str:
        # KEEP THIS TOP PORTION AS IS |
        #                             V
        if not os.path.exists(folderPath):
            os.makedirs(folderPath)
        songBasePath: str = os.path.join(folderPath, self.id)
        songPath: str = f"{songBasePath}.mp3"
        if os.path.exists(songPath):
            return songPath
        elif self.__filePath != None and os.path.exists(self.__filePath):
            return self.__filePath
        #                             ^
        # THANK YOU                   |
        ytdl_opts = {
            'format': 'bestaudio/best',         # Get the best audio quality
            'extractaudio': True,               # Extract audio only
            'audioformat': 'mp3',               # Convert to MP3 format
            'noplaylist': True,                 # Don't download playlists
            'quiet': True,                      # Suppress console output for faster processing
            'no_warnings': True,                # Suppress warnings
            'postprocessors': [{                # Post-process audio to convert to MP3
                'key': 'FFmpegExtractAudio',
                'preferredcodec': 'mp3',
                'preferredquality': '128',      # Audio quality (bitrate)
            }],
            'default_search': 'ytsearch1',       # Limit search to the first result
            'outtmpl': songBasePath
        }
        query: str = f'{self.artists[0]} {self.title} audio'
        with yt_dlp.YoutubeDL(ytdl_opts) as ytdl:
            try:
                ytdl.download([query])
            except Exception as e:
                print(f'YT Download Error: {e}')
        if os.path.exists(songPath):
            self.__filePath = songPath
        return self.__filePath
    
    def getEmbed(self, title: str = None) -> discord.Embed:
        footerText: str = None
        artistList: str = ''
        for i, artist in enumerate(self.artists):
            if i == 0:
                artistList += artist
            else:
                artistList += f', {artist}'
        embed = discord.Embed(
            title=(title if title else 'Now Playing'),
            description=(f'{self.title} \nby {artistList}\n'),
            colour=discord.Color.fuchsia()
        )
        embed.set_thumbnail(url=self.thumbnailUrl)
        if self.requestor.bot:
            footerText = 'Recommended song'
        else:
            footerText = f'Queued by {self.requestor.display_name}'
        embed.set_footer(text=footerText, icon_url=self.requestor.display_avatar)
        return embed


class DiscordPlayer(discord.ui.View):
    def __init__(self, guildID: int, folderPath: str):
        super().__init__(timeout=None)
        self.id: int = guildID
        self.folderPath: str = folderPath

        self.__voiceClient: discord.VoiceClient = None
        self.__txtChannel: discord.TextChannel = None
        self.__nowPlayingMsg: discord.Message = None
        self.__currentSong: Song = None
        self.__lastQueuedSong: Song = None
        self.__resendMsg: bool = False
        self.__songQueue: list[Song] = []   # FIFO
        self.__recQueue: list[Song] = []    # FIFO
        self.__history: list[Song] = []     # LIFO

        self.__spotify = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(client_id=os.environ.get('SPOTIFY_API_KEY'),
            client_secret=os.environ.get('SPOTIFY_SECRET_API_KEY')))
        self.__lastFM = pylast.LastFMNetwork(
            api_key=os.environ.get('LASTFM_API_KEY'),
            api_secret=os.environ.get('LASTFM_SECRET_API_KEY'),
            username=os.environ.get('LASTFM_USERNAME'),
            password_hash=(pylast.md5(os.environ.get('LASTFM_PASSWORD'))))

    @discord.ui.button(emoji='⏯', style=discord.ButtonStyle.grey)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.__voiceClient.is_paused():
            self.__voiceClient.resume()
            await self.sendNowPlayingMsg()
        elif self.__voiceClient.is_playing():
            self.__voiceClient.pause()
            await self.__nowPlayingMsg.edit(embed=self.getPausedEmbed(avatar=interaction.user.display_avatar))

    @discord.ui.button(emoji='⏩', style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.edit(embed=self.getLoadingEmbed())
        self.loopChecker(loop=interaction.client.loop)

    async def clearQueues(self) -> None:
        self.__resendMsg = False
        self.__lastQueuedSong = None
        if len(self.__songQueue) > 0:
            self.__songQueue.clear()
        if len(self.__recQueue) > 0:
            self.__recQueue.clear()
        if len(self.__history) > 0:
            self.__history.clear()
        if self.__nowPlayingMsg:
            await self.__nowPlayingMsg.delete()
            self.__nowPlayingMsg = None
        self.__txtChannel = None

    async def disconnect(self) -> None:
        if self.__voiceClient:
            self.__voiceClient.stop()
            await self.__voiceClient.disconnect()
            self.__voiceClient = None
        await self.clearQueues()

    async def queueSong(self, song: Song, interaction: discord.Interaction) -> None:
        if self.__voiceClient is None or self.__voiceClient.is_connected() is False:
            await self.disconnect()
            try:
                self.__voiceClient = await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f'Failed to connect to voice.')
                print(f'VOICE CONNECTION ERROR: {e}')
                await self.disconnect()
                return
                
        self.__txtChannel = interaction.channel
        self.__lastQueuedSong = song
        self.__resendMsg = True
        if self.__voiceClient.is_playing():
            self.__songQueue.append(song)
            await interaction.followup.send(f'Queued {song.title} by {song.artists[0]}.')
        else:
            if self.__nowPlayingMsg:
                await self.__nowPlayingMsg.delete()
                self.__nowPlayingMsg = None
            self.__nowPlayingMsg = await interaction.followup.send(embed=song.getEmbed(title='Loading...'), view=self)
            self.__recQueue.clear()
            self.playSong(song=song, loop=interaction.client.loop)

    def pushPrevious(self, song: Song) -> None:
        if song != None:
            if len(self.__history) > 18:
                poppedSong = self.__history.pop(len(self.__history) - 1)
                poppedSong.deleteFile()
            self.__history.insert(0, song)
    
    def popSong(self) -> Song:
        if len(self.__songQueue) > 0:
            self.__recQueue.clear()
            return self.__songQueue.pop(0)
        elif len(self.__recQueue) > 0:
            self.__lastQueuedSong = None
            return self.__recQueue.pop(0)
        else:
            if self.__lastQueuedSong:
                if not self.getRecSongs(comparableSong=self.__lastQueuedSong):
                    self.__lastQueuedSong = None
                    return self.popSong()
            else:
                for track in self.__history:
                    if self.getRecSongs(comparableSong=track):
                        break
            return self.__recQueue.pop(0)

    def getChannelLength(self) -> int:
        if self.__voiceClient and self.__voiceClient.is_connected():
            return len(self.__voiceClient.channel.members)
        return -1
    
    def getArtistCompare(self, artist: str) -> bool:
        try:
            topTracksList = self.__lastFM.get_artist(artist_name=artist).get_top_tracks(limit=10)
            if len(topTracksList) == 0 or topTracksList is None:
                return False    # Try similar artist?
        except Exception as e:
            print(e)
            
        chosenSong: pylast.Track = choice(topTracksList).item
        while not self.recentlyPlayed(chosenSong.get_name()):
            chosenSong = choice(topTracksList).item
        
        trackInfo = self.__spotify.search(q=(f'{chosenSong.get_artist()} {chosenSong.get_name()}'), limit=1, type=['track'])['tracks']['items'][0]
        artistsList: [str] = []
        for artist in trackInfo['artists']:
            artistsList.append(artist['name'])
        recSong = Song(id=trackInfo['id'], title=trackInfo['name'], artists=artistsList, requestor=self.__voiceClient.user, duration=trackInfo['duration_ms'],
            thumbnailUrl=trackInfo['album']['images'][len(trackInfo['album']['images'])-1]['url'])
        self.__recQueue.clear()
        self.__recQueue.append(recSong)
        if len(self.__recQueue) > 0: return True
        else: return False

    def getRecSongs(self, comparableSong: Song) -> bool:
        similarSongList: [pylast.SimilarItem] = None
        try:
            trackObj: pylast.Track = self.__lastFM.get_track(artist=comparableSong.artists[0], title=comparableSong.title)
            similarSongList = trackObj.get_similar(limit=20)
            if len(similarSongList) == 0 or similarSongList is None:
                print("get_similar songs failed")
                return self.getArtistCompare(artist=comparableSong.artists[0])
        except Exception as e:
            return self.getArtistCompare(artist=comparableSong.artists[0])
        
        recSongs: dict =  {'most': [], 'middle': [], 'least': []}
        def matchSimilarity(track: pylast.Track, similarity: float):
            if float(similarity) >= float(0.80):
                recSongs.get('most').append(track)
            elif float(similarity) > float(0.15):
                recSongs.get('middle').append(track)
            else:
                recSongs.get('least').append(track)

        for track, similarity in similarSongList:
            if self.recentlyPlayed(str(track.get_name())):
                continue
            matchSimilarity(track=track, similarity=similarity)

        self.__recQueue.clear()
        queuedSongs: [str] = list()
        for key, adjList in recSongs.items():
            tierCensus: int = int(ceil(len(adjList) / float(2)))
            i: int = 0
            while i < tierCensus:
                i+=1
                chosenSong: pylast.Track = adjList.pop(randint(0, len(adjList)-1))
                query: str = f'{chosenSong.get_artist()} {chosenSong.get_name()}'
                queuedSongs.append(query)
                trackInfo = self.__spotify.search(q=query, limit=1, type=['track'])['tracks']['items'][0]
                artistsList: [str] = []
                for artist in trackInfo['artists']:
                    artistsList.append(artist['name'])
                recSong = Song(id=trackInfo['id'], title=trackInfo['name'], artists=artistsList, requestor=self.__voiceClient.user, duration=trackInfo['duration_ms'],
                    thumbnailUrl=trackInfo['album']['images'][len(trackInfo['album']['images'])-1]['url'])
                self.__recQueue.append(recSong)
        print(f'Queued Songs: {queuedSongs}')
        if len(self.__recQueue) > 0:
            return True
        else:
            return False
        
    def recentlyPlayed(self, title: str) -> bool:
        if len(self.__history) < 1: return False
        for track in self.__history:
            if title.find(track.title) != -1:
                return True
        return False

    def playSong(self, song: Song, loop) -> None:
        if song is None:
            print("Error: Song is Null!")
            print(f"Length of recQueue: {len(self.__recQueue)}")
            return
        try:
            songFilePath: str = song.getFilePath(folderPath=self.folderPath)
        except Exception as e:
            print(f'Caught exception: {e}')

        run_coroutine_threadsafe(self.sendNowPlayingMsg(song=song), loop)
        self.__currentSong = song
        FFmpegOptions = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
            'options': '-vn'}

        audio: discord.AudioSource = discord.PCMVolumeTransformer(
                original=discord.FFmpegPCMAudio(source=songFilePath,
                    executable='ffmpeg',
                    pipe=False,
                    options=FFmpegOptions),
                volume=float(1.0))
        self.__voiceClient.play(
            source=audio,
            after=lambda e: self.loopChecker(loop),
            application='audio',
            bitrate=128,
            fec=True,
            expected_packet_loss=float(0.15),
            bandwidth='full',
            signal_type='music')

    def loopChecker(self, loop) -> None:
        if self.__voiceClient is None:
            return
        elif self.__voiceClient.is_connected():
            if self.__voiceClient.is_playing():
                self.__voiceClient.pause()
            self.pushPrevious(song=self.__currentSong)
            self.playSong(song=self.popSong(), loop=loop)
        else:
            self.__voiceClient.stop()

    async def sendNowPlayingMsg(self, song: Song = None) -> None:
        if self.__txtChannel and (song or self.__currentSong):
            if not self.__resendMsg and self.__nowPlayingMsg:
                await self.__nowPlayingMsg.edit(embed=(song.getEmbed() if song else self.__currentSong.getEmbed()))
            else:
                if self.__nowPlayingMsg:
                    await self.__nowPlayingMsg.delete()
                    self.__nowPlayingMsg = None
                self.__nowPlayingMsg = await self.__txtChannel.send(embed=(song.getEmbed() if song else self.__currentSong.getEmbed()), view=self)
                self.__resendMsg = False
        else:
            print("Could not send nowPlayingMsg: idk fam")
    
    def getPausedEmbed(self, avatar) -> discord.Embed:
        pasuedEmbed: discord.Embed = discord.Embed(
            title='Music Paused',
            colour=discord.Color.dark_gold()
        )
        pasuedEmbed.set_thumbnail(url=self.__currentSong.thumbnailUrl)
        pasuedEmbed.set_footer(text= '', icon_url=avatar)
        return pasuedEmbed
    
    def getLoadingEmbed(self, title: str = None) -> discord.Embed:
        loadingEmbed: discord.Embed = discord.Embed(
            title=(title if title else 'Loading...'),
            colour=discord.Color.fuchsia()
        )
        return loadingEmbed

