"""Music Player functionality"""
import os
import discord
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from song import Song, SpotifySong, SoundcloudSong
from embeds import getLoadingEmbed, getPausedEmbed, getPlayingEmbed, getErrorEmbed
from asyncio import run_coroutine_threadsafe
from g4f import Client, Provider
import re


INSTRUCTIONS: str = 'You are a song recommender, your response needs to be a numbered list with no markdown in the format artist - title'
AI_MODEL: str = 'gemini-1.5-flash'

class DiscordPlayer(discord.ui.View):
    def __init__(self, guildID: int, folderPath: str):
        super().__init__(timeout=None)
        self.id: int = guildID
        self.folderPath: str = folderPath
        self.disconnecting: bool = False

        self.__voiceClient: discord.VoiceClient = None
        self.__txtChannel: discord.TextChannel = None
        self.__nowPlayingMsg: discord.Message = None
        self.__resendMsg: bool = False

        self.__currentSong: Song = None
        self.__songQueue: list[Song] = list()   # FIFO
        self.__recQueue: list[Song] = list()    # FIFO
        self.__history: list[Song] = list()     # LIFO

        self.__aiModel = Client(provider=Provider.TeachAnything)
        self.__spotify = spotipy.Spotify(
            auth_manager=SpotifyClientCredentials(client_id=os.environ.get('SPOTIFY_API_KEY'),
            client_secret=os.environ.get('SPOTIFY_SECRET_API_KEY')))


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
            await self.__sendMsg(embed=getPlayingEmbed(song=self.__currentSong))
        elif self.__voiceClient.is_playing():
            self.__voiceClient.pause()
            await self.__nowPlayingMsg.edit(embed=getPausedEmbed(song=self.__currentSong, user=interaction.user))


    @discord.ui.button(emoji='⏩', style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.__currentSong.skipped = True
        await interaction.message.edit(embed=getLoadingEmbed())
        self.__loopChecker(loop=interaction.client.loop)


    async def __clearQueues(self) -> None:
        # Clears song queue and deletes queue controls
        self.__resendMsg = False
        if len(self.__songQueue) > 0:
            self.__songQueue.clear()
        if len(self.__recQueue) > 0:
            self.__recQueue.clear()
        if len(self.__history) > 0:
            self.__history.clear()
        if self.__nowPlayingMsg:
            try:
                await self.__nowPlayingMsg.delete()
            except:
                pass
            self.__nowPlayingMsg = None
        self.__txtChannel = None


    async def disconnect(self) -> None:
        # Disconnects bot from voice channel
        if self.__voiceClient:
            try:
                self.__voiceClient.stop()
                await self.__voiceClient.disconnect()
            except Exception as e:
                print(e)
            self.__voiceClient = None
        await self.__clearQueues()


    async def queueSong(self, song: Song, interaction: discord.Interaction) -> None:
        # Initializes the voice client, 
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
        self.__resendMsg = True
        self.__songQueue.append(song)
        await interaction.followup.send(f'Queued {song.title} by {song.getArtistList()}.')
        if not self.__voiceClient.is_playing():
            self.__loopChecker(loop=interaction.client.loop)


    def __pushPrevious(self, song: Song) -> None:
        # Adds the given song to the history queue
        if song != None:
            if len(self.__history) > 25:
                poppedSong = self.__history.pop(len(self.__history) - 1)
                if type(poppedSong) is SpotifySong:
                    poppedSong.deleteFile()
            self.__history.insert(0, song)
    
    
    def __popSong(self) -> Song:
        # Pops the next song in the queue
        if len(self.__songQueue) > 0:
            self.__recQueue.clear()
            return self.__songQueue.pop(0)
        elif len(self.__recQueue) > 0:
            return self.__recQueue.pop(0)
        else:
            if self.__getRecSongs(limit=13):
                return self.__recQueue.pop(0)
            else:
                return None


    def getChannelLength(self) -> int:
        # Returns the amount of users in the voice client's channel, used for auto-disconnect
        if self.__voiceClient:
            return len(self.__voiceClient.channel.members)
        return -1
    

    def recentlyPlayed(self, title: str) -> bool:
        # Returns True if the given song title was recently played
        target: str = title.lower()
        if len(self.__history) < 1: return False
        for track in self.__history:
            pastTitle: str = track.title.lower()
            if pastTitle == target:
                return True
            elif target in pastTitle:
                return True
            elif pastTitle in target:
                return True
        return False


    def __playSong(self, song: Song, loop) -> None:
        # Normalizes audio levels and plays the song
        songFilePath: str = None
        if song is None or not isinstance(song, Song):
            run_coroutine_threadsafe(self.__sendMsg(embed=getErrorEmbed()), loop)
            return
        else:
            try:
                songFilePath = song.getAudioPath()
            except:
                pass
        if songFilePath is None:
            run_coroutine_threadsafe(self.__sendMsg(embed=getErrorEmbed(title='Could Not Download Song')), loop)
            return

        FFmpegOptions = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
                        'options': '-vn'}
        self.__currentSong = song
        run_coroutine_threadsafe(self.__sendMsg(embed=getPlayingEmbed(song=song)), loop)
        audio: discord.AudioSource = discord.PCMVolumeTransformer(
                original=discord.FFmpegPCMAudio(
                    source=songFilePath,
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
        # Called inbetween songs, prevents errors
        if self.__voiceClient == None or self.__voiceClient.is_connected() == False:
            run_coroutine_threadsafe(self.disconnect(), loop)
            return
        else:
            if self.__voiceClient.is_playing():
                self.__voiceClient.pause()
            if self.__currentSong:
                self.__pushPrevious(song=self.__currentSong)
            if self.__nowPlayingMsg == None:
                self.__resendMsg = True
            self.__playSong(song=self.__popSong(), loop=loop)


    async def __sendMsg(self, embed: discord.Embed) -> None:
        # Sends the given embed in a text channel
        if self.__nowPlayingMsg is None:
            self.__nowPlayingMsg = await self.__txtChannel.send(embed=embed, view=self)
        elif self.__resendMsg:
            try:
                await self.__nowPlayingMsg.delete()
            except:
                pass
            self.__nowPlayingMsg = await self.__txtChannel.send(embed=embed, view=self)
            self.__resendMsg = False
        else:
            await self.__nowPlayingMsg.edit(embed=embed)
    


    def __getRecSongs(self, limit: int=10) -> bool:
        # Fills the queue with recommended songs
        prompt: str = f'Give me {limit} song recommendations similar to these songs:\n'
        if len(self.__history) > 1:
            # Until the last user-queued song, get all the songs the user didnt skip
            for track in self.__history:
                if not track.requestor.bot:
                    prompt += f'{track.title} by {track.getArtistList()}\n'
                    break
                elif not track.skipped:
                        prompt += f'{track.title} by {track.getArtistList()}\n'
        elif self.__currentSong:
            prompt += f'{self.__currentSong.title} by {self.__currentSong.getArtistList()}\n'
        else:
            return False

        response = self.__aiModel.chat.completions.create(
            messages=[{'role':'system', 'content':INSTRUCTIONS},
                      {'role':'user', 'content':prompt}],
            model=AI_MODEL
        )

        def __extractSongs(rawResponse: str) -> bool:
            # Gets the Spotify songs from the response
            for line in rawResponse.splitlines():
                match = re.search(r"(\d+\.\s*)(.*?)\s*-\s*(.*)", line) 
                if match:
                    matchTitle: str = match.group(3).strip()
                    matchArtist: str = match.group(2).strip()
                    if not self.recentlyPlayed(title=matchTitle):
                        trackInfo: object = None
                        try:
                            trackInfo = self.__spotify.search(q=(f'{matchTitle} {matchArtist}'), limit=1, type=['track'])['tracks']['items'][0]
                        except:
                            continue
                        artistsList: list[str] = list()
                        for artist in trackInfo['artists']:
                            artistsList.append(artist['name'])
                        recSong = SpotifySong(id=trackInfo['id'], title=trackInfo['name'], artists=artistsList, requestor=self.__voiceClient.user,
                                              guildFolderPath=self.folderPath, duration=trackInfo['duration_ms'],
                                              thumbnailUrl=trackInfo['album']['images'][len(trackInfo['album']['images'])-1]['url'], explicit=trackInfo['explicit'])
                        self.__recQueue.append(recSong)
            if len(self.__recQueue) > 0: return True
            else: return False

        return __extractSongs(rawResponse=response.choices[0].message.content)



