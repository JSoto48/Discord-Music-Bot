import yt_dlp as youtube_dl
import discord
import pylast
from os import environ
from discord.ext import commands
from asyncio import run_coroutine_threadsafe


class Song():
    def __init__(self, title: str, artist: str, requestor: discord.User = None):
        self.title: str = title
        self.artist: str = artist
        self.requestor: discord.User = requestor

        self.trackUrl: str = None
        # self.trackID: str = None
        self.thumbnailURL: str = None


    def getTrackUrl(self):
        query = f'{self.title} by {self.artist} song'
        ytdl_opts = {
            'format': 'bestaudio/best',         # Get the best audio quality
            'noplaylist': True,                 # Don't download playlists
            'quiet': True,                      # Show progress
            'default_search': 'ytsearch1',      # Limit search to the first result
            'no_warnings': True,                # Suppress warnings
        }

        with youtube_dl.YoutubeDL(ytdl_opts) as ytdl:
            trackInfo = ytdl.extract_info(query, download=False)
        self.trackUrl = trackInfo['entries'][0]['url']



class GuildInfo():
    def __init__(self, voiceClient: discord.VoiceClient):
        self.voiceClient: discord.VoiceClient = voiceClient
        self.nowPlayingMessage: discord.Message = None
        self.lastSong: Song = None
        self.messageCount: int = 0
        self.lastFM = pylast.LastFMNetwork(
            api_key=environ.get('LASTFM_API_KEY'),
            api_secret=environ.get('LASTFM_SECRET_API_KEY'),
            username=environ.get('LASTFM_USERNAME'),
            password_hash=(pylast.md5(environ.get('LASTFM_PASSWORD')))
        )

        self.__history: list[Song] = []     # LIFO
        self.__songQueue: list[Song] = []   # FIFO
        self.__recQueue: list[Song] = []    # FIFO
    
    async def clearQueues(self) -> None:
        if len(self.__songQueue) > 0:
            self.__songQueue.clear()
        if len(self.__recQueue) > 0:
            self.__recQueue.clear()
        if len(self.__history) > 0:
            self.__history.clear()
        if self.nowPlayingMessage is not None:
            await self.nowPlayingMessage.delete()
            self.nowPlayingMessage = None
        self.messageCount = 0
        self.lastSong = None

    def queueSong(self, track: Song) -> None:
        self.__songQueue.append(track)
        self.messageCount += 1

    def getSong(self) -> Song:
        poppedSong: Song = None
        if len(self.__songQueue) > 0:
            poppedSong = self.__songQueue.pop(0)
            self.__recQueue.clear()
        elif len(self.__recQueue) > 0:
            poppedSong = self.__recQueue.pop(0)
            self.lastSong = None
        else:
            self.__recQueue = self.getRecSongs()
            poppedSong = self.__recQueue.pop(0)
        self.lastSong = poppedSong
        return poppedSong

    
    def getRecSongs(self) -> list[Song]:
        trackObj: pylast.Track = None
        similarSongs: list[pylast.SimilarItem] = []
        songList: list[Song] = []
        # Get recommended songs, prioritize the last user-queued song
        if self.lastSong:
            trackObj = self.lastFM.get_track(artist=self.lastSong.artist, title=self.lastSong.title)
            similarSongs = trackObj.get_similar(limit=20)
            if similarSongs is None:
                self.lastSong = None
                print("No song recs from lastSong, re-calling on history")
                return self.getRecSongs()
        else:
            for song in self.__history:
                trackObj = self.lastFM.get_track(artist=song.artist, title=song.title)
                similarSongs = trackObj.get_similar(limit=20)
                if similarSongs is not None:
                    print("ELSE found rec songs")
                    break

        # Filter the recommended tracks
        for track in similarSongs:
            recSong = Song(title=str(track.item.title), artist=str(track.item.artist), requestor=self.voiceClient.user)
            songList.append(recSong)
        return songList
    

    
    def peekPrevious(self) -> Song:
        if len(self.__history) > 0:
            return self.__history[0]
    
    def popPrevious(self) -> Song:
        if len(self.__history) > 0:
            return self.__history.pop(0)
    
    def pushPrevious(self, song: Song) -> None:
        if song:
            if len(self.__history) > 20:
                self.__history.pop(len(self.__history) - 1)
            self.__history.insert(0, song)
            print(f'Pushed {song.title} to history.')



class QueueManager(discord.ui.View):
    def __init__(self, spotifyAPI, lastFM):
        self.spotifyAPI = spotifyAPI
        self.guilds: (int, GuildInfo) = {}
    
    
    @discord.ui.button(emoji='⏯', style=discord.ButtonStyle.grey)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc = self.guilds.get(interaction.guild_id).voiceClient
        if vc.is_paused():
            vc.resume()
        elif vc.is_playing():
            vc.pause()


    @discord.ui.button(emoji='⏩', style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        # vc = self.guilds.get(interaction.guild_id).voiceClient
        # if vc.is_playing():
        #     vc.pause()
        #     vc.stop()
        self.playNext(interaction=interaction)


    async def addToQueue(self, songName: str, songArtist:str, interaction: discord.Interaction):
        if not interaction.user.voice:
            await interaction.followup.send('Join a voice channel to play music')
            return

        guildInfo = self.guilds.get(interaction.guild_id)
        if guildInfo is None:
            try:
                newVoiceClient: discord.VoiceClient = await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f'Failed to connect to voice: {e}')
                return
            self.guilds.update({interaction.guild_id: GuildInfo(voiceClient=newVoiceClient)})
            guildInfo = self.guilds.get(interaction.guild_id)
        elif guildInfo.voiceClient is None or guildInfo.voiceClient.is_connected() is False:
            await guildInfo.clearQueues()
            try:
                newVoiceClient: discord.VoiceClient = await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f'Failed to connect to voice: {e}')
                return
            guildInfo.voiceClient = newVoiceClient

        newSong: Song = Song(title=songName, artist=songArtist, requestor=interaction.user)
        guildInfo.queueSong(newSong)
        await interaction.followup.send(f'Added {newSong.title} by {newSong.artist} to the queue')
        if guildInfo.voiceClient.is_playing() is False:
           self.playNext(interaction)
        

    def playNext(self, interaction: discord.Interaction, paramSong: Song = None):
        guildInfo = self.guilds.get(interaction.guild_id)
        nextSong: Song = None        
        if paramSong is None:
            nextSong = guildInfo.getSong()
            if nextSong is None:
                print(f'Error: null song - {nextSong}')
                return
        else:
            nextSong = paramSong

        run_coroutine_threadsafe(self.sendNowPlayingMessage(interaction, self.getNowPlayingEmbed(nextSong)), interaction.client.loop)
        if guildInfo.voiceClient.is_playing():
            guildInfo.voiceClient.pause()
        nextSong.getTrackUrl()

        FFmpegOptions = {'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
            'options': '-vn'}
        guildInfo.voiceClient.play(
            source=discord.FFmpegPCMAudio(
                source=nextSong.trackUrl,
                executable='ffmpeg',
                pipe=False,
                options=FFmpegOptions),
            after=lambda e: (self.playNext(interaction)),
            application='audio',
            bitrate=128,
            fec=True,
            expected_packet_loss=float(0.15),
            bandwidth='full',
            signal_type='music')
        guildInfo.pushPrevious(song=nextSong)
    

    # def loopChecker(self, guildID: int):
    #     guildInfo = self.guilds.get(guildID)
    #     if guildInfo.voiceClient.is_connected() is False:
    #         return
    #     else:
    #         self.playNext


    async def sendNowPlayingMessage(self, interaction: discord.Interaction, embed: discord.Embed) -> None:
        guildInfo = self.guilds.get(interaction.guild_id)
        if guildInfo.nowPlayingMessage is None:
            super().__init__(timeout=None)
            guildInfo.nowPlayingMessage = await interaction.channel.send(embed=embed, view=self)
        else:
            if guildInfo.messageCount > 3:
                await guildInfo.nowPlayingMessage.delete()
                guildInfo.nowPlayingMessage = await interaction.channel.send(embed=embed, view=self)
                guildInfo.messageCount = 0
            else:
                await guildInfo.nowPlayingMessage.edit(embed=embed)


    def getSongInfo(self, track: Song) -> Song:
        if track is None:
            print("empty track")
            return
        query = track.artist+' '+track.title
        apiCall = self.spotifyAPI.search(q=query, limit=1, type='track')
        results = apiCall['tracks']['items'][0]

        # track.trackID = results['uri']
        images = results['album']['images']
        track.thumbnailURL = images[len(images)-1]['url']
        return track


    def getNowPlayingEmbed(self, track: Song) -> discord.Embed:
        track = self.getSongInfo(track)
        embed = discord.Embed(
            title='Now Playing',
            description=(f'{track.title} \nby {track.artist}'),
            colour=discord.Color.fuchsia()
        )
        embed.set_thumbnail(url=track.thumbnailURL)

        footerText: str = None
        if track.requestor.bot:
            footerText = f'Recommended song'
        else:
            footerText = f'Queued by {track.requestor.name}'
        embed.set_footer(text=footerText, icon_url=track.requestor.avatar)
        return embed


    async def disconnect(self, guildID: int):
        guildInfo = self.guilds.get(guildID)
        if guildInfo.voiceClient.is_playing():
            guildInfo.voiceClient.stop()
        if guildInfo.voiceClient.is_connected():
            await guildInfo.voiceClient.disconnect()
        await guildInfo.clearQueues()
        guildInfo.voiceClient = None
        print('Disconnect Completed')


# @discord.ui.button(emoji='⏪', style=discord.ButtonStyle.grey)
    # async def previous(self, interaction: discord.Interaction, button: discord.ui.Button):
    #     await interaction.response.defer()
    #     guildInfo = self.guilds.get(interaction.guild_id)

    #     prevSong = guildInfo.popPrevious()
    #     if prevSong is None:
    #         guildInfo.voiceClient.stop()
    #         return
    #     else:
    #         self.playNext(interaction=interaction, paramSong=prevSong)


