import os
import pylast
import spotipy
import discord
from math import ceil
import yt_dlp as youtube_dl
from asyncio import run_coroutine_threadsafe
from random import choice

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
        # KEEP THIS TOP PORTION AS IS
        if not os.path.exists(folderPath):
            os.makedirs(folderPath)
        songBase: str = os.path.join(folderPath, self.id)
        songPath: str = f"{songBase}.mp3"
        if os.path.exists(songPath):
            return songPath
        elif self.__filePath != None and os.path.exists(self.__filePath):
            return self.__filePath
        # THANK YOU
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
            'outtmpl': songBase
        }
        query: str = f'{self.artists[0]} {self.title} audio'
        with youtube_dl.YoutubeDL(ytdl_opts) as ytdl:
            try:
                ytdl.download([query])
                if os.path.exists(songPath):
                    self.__filePath = songPath
                    return self.__filePath
            except Exception as e:
                print(f'YT Download Error: {e}')
    
    def getEmbed(self) -> discord.Embed:
        footerText: str = None
        artistList: str = ''
        for i, artist in enumerate(self.artists):
            if i == 0:
                artistList += artist
            else:
                artistList += f', {artist}'
        embed = discord.Embed(
            title='Now Playing',
            description=(f'{self.title} \nby {artistList}\n'),
            colour=discord.Color.fuchsia()
        )
        embed.set_thumbnail(url=self.thumbnailUrl)
        if self.requestor.bot:
            footerText = 'Recommended song'
        else:
            footerText = f'Queued by {self.requestor.name}'
        embed.set_footer(text=footerText, icon_url=self.requestor.avatar)
        return embed


class GuildPlayer(discord.ui.View):
    def __init__(self, guildID: int, folderPath: str, eventLoop,
    lastFM: pylast.LastFMNetwork, spotify: spotipy.Spotify,
    voiceClient: discord.VoiceClient = None, msgChannel: discord.TextChannel = None):
        super().__init__(timeout=None)
        self.id: int = guildID
        self.__folderPath: str = folderPath
        self.__loop = eventLoop
        self.__lastFM = lastFM
        self.__spotify = spotify
        self.voiceClient: discord.VoiceClient = voiceClient
        self.txtChannel: discord.TextChannel = msgChannel

        self.nowPlayingMsg: discord.Message = None
        self.lastQueuedSong: Song = None
        self.msgCount: int = 0
        self.__songQueue: list[Song] = []   # FIFO
        self.__recQueue: list[Song] = []    # FIFO
        self.__history: list[Song] = []     # LIFO


    @discord.ui.button(emoji='⏯', style=discord.ButtonStyle.grey)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.voiceClient.is_paused():
            self.voiceClient.resume()
        elif self.voiceClient.is_playing():
            self.voiceClient.pause()

    @discord.ui.button(emoji='⏩', style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.loopChecker()

    async def clearQueues(self) -> None:
        self.msgCount = 0
        self.lastQueuedSong = None
        if len(self.__songQueue) > 0:
            self.__songQueue.clear()
        if len(self.__recQueue) > 0:
            self.__recQueue.clear()
        if len(self.__history) > 0:
            self.__history.clear()
        if self.nowPlayingMsg is not None:
            await self.nowPlayingMsg.delete()
            self.nowPlayingMsg = None

    async def disconnect(self) -> None:
        if self.voiceClient.is_connected():
            if self.voiceClient.is_playing():
                self.voiceClient.stop()
            await self.voiceClient.disconnect()
        self.voiceClient = None
        await self.clearQueues()
        for fileName in os.listdir(self.__folderPath):
            filePath = os.path.join(self.__folderPath, fileName)
            try:
                if os.path.isfile(filePath) or os.path.islink(filePath):
                    os.unlink(filePath)
            except Exception as e:
                print(f'Failed to delete {filePath}.\n{e}\n')

    def queueSong(self, song: Song) -> None:
        self.__songQueue.append(song)
        self.lastQueuedSong = song
        self.msgCount += 1
    
    def pushPrevious(self, song: Song) -> None:
        if song != None:
            if len(self.__history) > 18:
                poppedSong = self.__history.pop(len(self.__history) - 1)
                poppedSong.deleteFile()
            self.__history.insert(0, song)
            print(f'Pushed {song.title} to history.')
    
    def popSong(self) -> Song:
        if len(self.__songQueue) > 0:
            self.__recQueue.clear()
            return self.__songQueue.pop(0)
        elif len(self.__recQueue) > 0:
            self.lastQueuedSong = None
            return self.__recQueue.pop(0)
        else:
            print('Finding rec songs from pop()')
            if self.lastQueuedSong is None:
                for track in self.__history:
                    firstRecSong = self.getRecSongs(comparableSong=track)
                    if firstRecSong != None:
                        return self.__recQueue.pop(0)
            else:
                firstRecSong = self.getRecSongs(comparableSong=self.lastQueuedSong)
                if firstRecSong is None:
                    self.lastQueuedSong = None
                    return self.popSong()
                else:
                    return self.__recQueue.pop(0)
    
    def bufferNextSong(self) -> None:
        nextSong: Song = None
        if len(self.__songQueue) > 0:
            nextSong = self.__songQueue[0]
        elif len(self.__recQueue) > 0:
            nextSong = self.__recQueue[0]
        else:
            print('Finding rec songs from buffer()')
            if self.lastQueuedSong is None:
                for track in self.__history:
                    print(track.title)
                    nextSong = self.getRecSongs(comparableSong=track)
                    if nextSong != None:
                        break
            else:
                nextSong = self.getRecSongs(comparableSong=self.lastQueuedSong)
                if nextSong is None:
                    self.lastQueuedSong = None
                    return self.bufferNextSong()
        nextSong.getFilePath(folderPath=self.__folderPath)
    
    def getRecSongs(self, comparableSong: Song) -> Song:
        trackObj: pylast.Track = self.__lastFM.get_track(artist=comparableSong.artists[0], title=comparableSong.title)
        similarSongList: list[pylast.SimilarItem] = trackObj.get_similar(limit=20)
        if similarSongList is None: return None

        # Hash tracks by similarity
        recSongs: dict =  {'most': [], 'middle': [], 'least': []}
        def matchSimilarity(songStr: str, similarFloat: float):
            if float(similarFloat) >= float(0.80):
                recSongs.get('most').append(songStr)
            elif (float(similarFloat) < float(0.80)) and (float(similarFloat) > float(0.15)):
                recSongs.get('middle').append(songStr)
            else:
                recSongs.get('least').append(songStr)

        # Weed out repeated songs from history
        for track, similarity in similarSongList:
            tempTitle: str = track.get_title()
            tempArtist: str = track.get_artist()
            if self.lastQueuedSong != None:
                if tempTitle.find(self.lastQueuedSong.title) == -1:
                    matchSimilarity(songStr=f'{tempArtist}@#{tempTitle}', similarFloat=similarity)
                else:
                    print(f"Repeat Song: {tempTitle}")
            elif len(self.__history) > 0:
                for pastSong in self.__history:
                    if tempTitle.find(self.lastQueuedSong.title) == -1:
                        matchSimilarity(songStr=f'{tempArtist}@#{tempTitle}', similarFloat=similarity)
                    else:
                        print(f"Repeat Song: {tempTitle}")
            else:
                matchSimilarity(songStr=f'{tempArtist}@#{tempTitle}', similarFloat=similarity)
        
        # Initialize Song objects and grab songs based on similarity
        for key, adjList in recSongs.items():
            amt: int = int(ceil(len(adjList) / float(2)))       # int division, rounding up
            i: int = 0
            while i < amt:                                      # Idea here if to get a bell curve
                i+=1
                randSong: str = choice(adjList)
                adjList.remove(randSong)
                
                spotifyTrack = self.__spotify.search(q=f"{randSong.split('@#')[0]} {randSong.split('@#')[1]}", type=['track'])
                trackInfo = spotifyTrack['tracks']['items'][0]
                artistsList: [str] = []
                for artist in trackInfo['artists']:
                    artistsList.append(artist['name'])
                recSong = Song(id=trackInfo['id'], title=trackInfo['name'], artists=artistsList, requestor=self.voiceClient.user, duration=trackInfo['duration_ms'],
                    thumbnailUrl=trackInfo['album']['images'][len(trackInfo['album']['images'])-1]['url'])
                self.__recQueue.append(recSong)
        return self.__recQueue[0]

    def playSong(self, song: Song) -> None:
        if song is None:
            print("Error: Song is Null!")
            print(f"Length of recQueue: {len(self.__recQueue)}")
            return
        
        run_coroutine_threadsafe(self.sendNowPlayingMsg(songEmbed=song.getEmbed()), loop=self.__loop)
        FFmpegOptions = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
            'options': '-vn'}
        audio: discord.AudioSource = discord.PCMVolumeTransformer(
                original=discord.FFmpegPCMAudio(source=song.getFilePath(folderPath=self.__folderPath),
                    executable='ffmpeg',
                    pipe=False,
                    options=FFmpegOptions),
                volume=float(1.0))
        self.voiceClient.play(
            source=audio,
            after=lambda e: self.loopChecker(prevSong=song),
            application='audio',
            bitrate=128,
            fec=True,
            expected_packet_loss=float(0.15),
            bandwidth='full',
            signal_type='music')
        self.bufferNextSong()       # TODO: Laggy

    def loopChecker(self, prevSong: Song = None) -> None:
        if self.voiceClient.is_connected():
            if self.voiceClient.is_playing():
                self.voiceClient.pause()
            if prevSong is not None:
                self.pushPrevious(song=prevSong)
            self.playSong(song=self.popSong())
        else:
            if self.voiceClient is not None:
                self.voiceClient.stop()
            if self.__loop != None:
                run_coroutine_threadsafe(self.clearQueues(), loop=self.__loop)

    async def sendNowPlayingMsg(self, songEmbed: discord.Embed) -> None:
        if self.nowPlayingMsg is None:
            self.nowPlayingMsg = await self.txtChannel.send(embed=songEmbed, view=self)
            self.msgCount = 0
        elif self.msgCount > 1:
            await self.nowPlayingMsg.delete()
            self.nowPlayingMsg = await self.txtChannel.send(embed=songEmbed, view=self)
            self.msgCount = 0
        else:
            await self.nowPlayingMsg.edit(embed=songEmbed)
    
    

    