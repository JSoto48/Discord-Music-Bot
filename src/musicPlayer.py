import os
import spotipy
import discord
import messageEmbeds
from song import Song, SpotifySong
from asyncio import run_coroutine_threadsafe
from spotipy.oauth2 import SpotifyClientCredentials

import pylast
from math import ceil
from random import choice
from random import randint


class DiscordPlayer(discord.ui.View):
    def __init__(self, guildID: int, folderPath: str):
        super().__init__(timeout=None)
        self.id: int = guildID
        self.folderPath: str = folderPath
        self.disconnecting: bool = False

        self.__voiceClient: discord.VoiceClient = None
        self.__txtChannel: discord.TextChannel = None
        self.__nowPlayingMsg: discord.Message = None
        self.__currentSong: Song = None
        self.__lastQueuedSong: Song = None
        self.__resendMsg: bool = False
        self.__songQueue: list[Song] = list()   # FIFO
        self.__recQueue: list[Song] = list()    # FIFO
        self.__history: list[Song] = list()     # LIFO

        self.__spotify = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(client_id=os.environ.get('SPOTIFY_API_KEY'),
            client_secret=os.environ.get('SPOTIFY_SECRET_API_KEY')))
        self.__lastFM = pylast.LastFMNetwork(
            api_key=os.environ.get('LASTFM_API_KEY'),
            api_secret=os.environ.get('LASTFM_SECRET_API_KEY'),
            username=os.environ.get('LASTFM_USERNAME'),
            password_hash=(pylast.md5(os.environ.get('LASTFM_PASSWORD'))))


    @discord.ui.button(emoji='⏪', style=discord.ButtonStyle.grey)
    async def rewind(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        prevSong: Song = None
        if len(self.__history) > 0:
            prevSong = self.__history.pop(0)
            self.__recQueue.insert(0, self.__currentSong)
        else:
            prevSong = self.__currentSong
        
        if self.__voiceClient.is_playing():
            self.__voiceClient.pause()
        self.__playSong(song=prevSong, loop=interaction.client.loop)


    @discord.ui.button(emoji='⏯', style=discord.ButtonStyle.grey)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.__voiceClient.is_paused():
            self.__voiceClient.resume()
            await self.__sendNowPlayingMsg(song=self.__currentSong)
        elif self.__voiceClient.is_playing():
            self.__voiceClient.pause()
            await self.__nowPlayingMsg.edit(embed=messageEmbeds.getPausedEmbed(song=self.__currentSong, user=interaction.user))


    @discord.ui.button(emoji='⏩', style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        await interaction.message.edit(embed=messageEmbeds.getLoadingEmbed())
        self.__loopChecker(loop=interaction.client.loop)


    async def __clearQueues(self) -> None:
        self.__resendMsg = False
        self.__lastQueuedSong = None
        if len(self.__songQueue) > 0:
            self.__songQueue.clear()
        if len(self.__recQueue) > 0:
            self.__recQueue.clear()
        if len(self.__history) > 0:
            self.__history.clear()
        if self.__nowPlayingMsg:
            try:
                await self.__nowPlayingMsg.delete()
            except Exception as e:
                print(e)
            self.__nowPlayingMsg = None
        self.__txtChannel = None


    async def disconnect(self) -> None:
        if self.__voiceClient:
            try:
                self.__voiceClient.stop()
                await self.__voiceClient.disconnect()
            except Exception as e:
                print(e)
            self.__voiceClient = None
        await self.__clearQueues()


    async def queueSong(self, song: Song, interaction: discord.Interaction) -> None:
        if self.__voiceClient == None or self.__voiceClient.is_connected() == False:
            await self.disconnect()
            try:
                self.__voiceClient = await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f'Failed to connect to voice channel.')
                print(f'VOICE CONNECTION ERROR: {e}')
                await self.disconnect()
                return
                
        self.__txtChannel = interaction.channel
        self.__lastQueuedSong = song
        self.__resendMsg = True
        self.__songQueue.append(song)
        await interaction.followup.send(f'Queued {song.title} by {song.getArtistList()}.')
        if not self.__voiceClient.is_playing():
            self.__loopChecker(loop=interaction.client.loop)

    #TODO: Other song types
    def __pushPrevious(self, song: Song) -> None:
        if song != None:
            if len(self.__history) > 20:
                poppedSong = self.__history.pop(len(self.__history) - 1)
                if type(poppedSong) is SpotifySong:
                    poppedSong.deleteFile()
            self.__history.insert(0, song)
    
    
    def __popSong(self) -> Song:
        if len(self.__songQueue) > 0:
            self.__recQueue.clear()
            return self.__songQueue.pop(0)
        elif len(self.__recQueue) > 0:
            self.__lastQueuedSong = None
            return self.__recQueue.pop(0)
        else:
            if self.__lastQueuedSong:
                if not self.getRecSongs(comparableSong=self.__lastQueuedSong):
                    if not self.getArtistCompare(artist=self.__lastQueuedSong.artists[0]):
                        self.__lastQueuedSong = None
                        return self.__popSong()
            else:
                for track in self.__history:
                    if self.getRecSongs(comparableSong=track):
                        break
            return self.__recQueue.pop(0)


    def getChannelLength(self) -> int:
        if self.__voiceClient:
            return len(self.__voiceClient.channel.members)
        return -1
    
    #TODO: Doesnt work
    def recentlyPlayed(self, title: str) -> bool:
        target: str = title.lower()
        if len(self.__history) < 1: return False
        for track in self.__history:
            pastTitle: str = track.title.lower()
            if pastTitle == target:
                return True
            elif pastTitle.find(target) != -1:
                return True
            elif target.find(pastTitle) != -1:
                return True
        return False


    def __playSong(self, song: Song, loop) -> None:
        songFilePath: str = ''
        if song is None:
            print("Error: Song is Null!")
            return
        elif type(song) is SpotifySong:
            try:
                songFilePath: str = song.getFilePath(folderPath=self.folderPath)
                if songFilePath == None:
                    return
            except Exception as e:
                print(f'Caught exception: {e}')

        run_coroutine_threadsafe(self.__sendNowPlayingMsg(song), loop)
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
            after=lambda e: self.__loopChecker(loop),
            application='audio',
            bitrate=128,
            fec=True,
            expected_packet_loss=float(0.15),
            bandwidth='full',
            signal_type='music')


    def __loopChecker(self, loop) -> None:
        if self.__voiceClient == None or self.__voiceClient.is_connected() == False:
            # TODO: reconnect?
            return
        else:
            if self.__voiceClient.is_playing():
                self.__voiceClient.pause()
            if self.__currentSong:
                self.__pushPrevious(song=self.__currentSong)
            if self.__nowPlayingMsg == None:
                self.__resendMsg = True
            self.__playSong(song=self.__popSong(), loop=loop)


    async def __sendNowPlayingMsg(self, song: Song) -> None:
        # TODO: Change to send message and accept an embed, that way we can pass the loading embed with custom text if needed for errors in plaly
        if self.__nowPlayingMsg is None:
            self.__nowPlayingMsg = await self.__txtChannel.send(embed=messageEmbeds.getPlayingEmbed(song), view=self)
        elif self.__resendMsg:
            try:
                await self.__nowPlayingMsg.delete()
            except Exception as e:
                print(e)
            self.__nowPlayingMsg = await self.__txtChannel.send(embed=messageEmbeds.getPlayingEmbed(song), view=self)
            self.__resendMsg = False
        else:
            await self.__nowPlayingMsg.edit(embed=messageEmbeds.getPlayingEmbed(song))
    




    def getArtistCompare(self, artist: str, count: int = 10) -> bool:
        try:
            topTracksList = self.__lastFM.get_artist(artist_name=artist).get_top_tracks(limit=count)
        except Exception as e:
            print(e)
        if len(topTracksList) < 1 or topTracksList is None:         # if len < count then swap to next artist in list
            print('artist compare failed')
            return False
            
        chosenSong: pylast.Track = choice(topTracksList).item
        moreSongs: bool = False
        if self.recentlyPlayed(chosenSong.get_name()):
            moreSongs: bool = True
            for topTrack in topTracksList:
                if not self.recentlyPlayed(topTrack.item.get_name()):
                    chosenSong = topTrack.item
                    moreSongs = False
                    break
        if moreSongs:
            return self.getArtistCompare(artist=artist, count=(count*2))
        
        trackInfo = self.__spotify.search(q=(f'{chosenSong.get_artist()} {chosenSong.get_name()}'), limit=1, type=['track'])['tracks']['items'][0]
        artistsList: list[str] = list()
        for artist in trackInfo['artists']:
            artistsList.append(artist['name'])
        recSong = SpotifySong(id=trackInfo['id'], title=trackInfo['name'], artists=artistsList, requestor=self.__voiceClient.user, duration=trackInfo['duration_ms'],
            thumbnailUrl=trackInfo['album']['images'][len(trackInfo['album']['images'])-1]['url'], explicit=trackInfo['explicit'])
        self.__recQueue.clear()
        self.__recQueue.append(recSong)
        if len(self.__recQueue) > 0: return True
        else: return False


    def getRecSongs(self, comparableSong: Song) -> bool:
        similarSongList: list[pylast.SimilarItem] = list()
        try:
            trackObj: pylast.Track = self.__lastFM.get_track(artist=comparableSong.artists[0], title=comparableSong.title)
            similarSongList = trackObj.get_similar(limit=20)
        except Exception as e:
            return self.getArtistCompare(artist=comparableSong.artists[0])
        if similarSongList is None or len(similarSongList) < 1:
            print("get_similar songs failed")
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
            if not self.recentlyPlayed(str(track.get_name())):
                matchSimilarity(track=track, similarity=similarity)

        self.__recQueue.clear()
        queuedSongs: list[str] = list()
        for key, adjList in recSongs.items():
            tierCensus: int = int(ceil(len(adjList) / float(2)))
            i: int = 0
            while i < tierCensus:
                i+=1
                chosenSong: pylast.Track = adjList.pop(randint(0, len(adjList)-1))
                query: str = f'{chosenSong.get_artist()} {chosenSong.get_name()}'
                queuedSongs.append(query)
                trackInfo = self.__spotify.search(q=query, limit=1, type=['track'])['tracks']['items'][0]
                artistsList: list[str] = list()
                for artist in trackInfo['artists']:
                    artistsList.append(artist['name'])
                recSong = SpotifySong(id=trackInfo['id'], title=trackInfo['name'], artists=artistsList, requestor=self.__voiceClient.user, duration=trackInfo['duration_ms'],
                    thumbnailUrl=trackInfo['album']['images'][len(trackInfo['album']['images'])-1]['url'], explicit=trackInfo['explicit'])
                self.__recQueue.append(recSong)
        print(f'Queued Songs: {queuedSongs}')
        if len(self.__recQueue) > 0: return True
        else: return False