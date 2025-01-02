import yt_dlp as youtube_dl
import discord
from discord.ext import commands
from asyncio import run_coroutine_threadsafe


class Song():
    def __init__(self, title: str, artist: str, requestor: discord.User = None):
        self.title: str = title
        self.artist: str = artist
        self.requestor: discord.User = requestor

        self.trackUrl: str = None
        self.trackID: str = None
        self.thumbnailURL: str = None


    def getTrackUrl(self) -> bool:
        query = f'{self.artist} {self.title}'
        ytdl_opts = {
            'format': 'bestaudio/best',         # Get the best audio quality
            'noplaylist': True,                 # Don't download playlists
            'quiet': True,                      # Show progress
            'default_search': 'ytsearch1',      # Limit search to the first result
            'no_warnings': True,                # Suppress warnings
        }

        with youtube_dl.YoutubeDL(ytdl_opts) as ytdl:
            trackInfo = ytdl.extract_info(query, download=False)
        if trackInfo is not None:
            self.trackUrl = trackInfo['entries'][0]['url']
            return True
        else: return False



class GuildInfo():
    def __init__(self, guildID:int, voiceClient: discord.VoiceClient = None):
        self.guildID:int = guildID
        self.voiceClient: discord.VoiceClient = voiceClient
        self.nowPlayingMessage = None

        self.__history: list[Song] = []     # LIFO
        self.__songQueue: list[Song] = []   # FIFO
        self.__recQueue: list[Song] = []    # FIFO
    

    def clearQueues(self) -> None:
        if len(self.__songQueue) > 0:
            self.__songQueue.clear()
        if len(self.__recQueue) > 0:
            self.__recQueue.clear()
        if len(self.__history) > 0:
            self.__history.clear()
        if self.nowPlayingMessage is not None:
            self.nowPlayingMessage.delete()
            self.nowPlayingMessage = None


    def queueSong(self, track: Song) -> None:
        if track.requestor is None:
            self.__recQueue.append(track)
        else:
            self.__songQueue.append(track)

    
    def getSong(self) -> Song:
        poppedSong: Song = None
        if len(self.__songQueue) > 0:
            poppedSong = self.__songQueue.pop(0)
            self.__recQueue.clear()
            self.__history.insert(0, poppedSong)    # Check history length to conserve memory
        elif len(self.__recQueue) > 0:
            poppedSong = self.__recQueue.pop(0)
            self.__history.insert(0, poppedSong)    # Check history length to conserve memory
        return poppedSong
    
    def peekPrevious(self) -> Song:
        if len(self.__history) > 0:
            return self.__history[0]
    
    def popPrevious(self) -> Song:
        if len(self.__history) > 0:
            return self.__history.pop(0)



class QueueManager(discord.ui.View):
    def __init__(self, spotifyAPI, lastFM):
        self.spotifyAPI = spotifyAPI
        self.lastFM = lastFM
        self.guilds: (int, GuildInfo) = {}

    
    @discord.ui.button(emoji='⏯', style=discord.ButtonStyle.grey)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        vc = self.guilds.get(interaction.guild_id).voiceClient
        if vc.is_paused():
            vc.resume()
        elif vc.is_playing():
            vc.pause()


    @discord.ui.button(emoji='⏭', style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.playNext(interaction)


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
            self.guilds.update({interaction.guild_id: GuildInfo(guildID=interaction.guild_id, voiceClient=newVoiceClient)})
            guildInfo = self.guilds.get(interaction.guild_id)
        elif guildInfo.voiceClient is None or not guildInfo.voiceClient.is_connected():
            guildInfo.clearQueues()
            try:
                newVoiceClient: discord.VoiceClient = await interaction.user.voice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f'Failed to connect to voice: {e}')
                return
            guildInfo.voiceClient = newVoiceClient

        newSong: Song = Song(title=songName, artist=songArtist, requestor=interaction.user)
        guildInfo.queueSong(newSong)
        await interaction.followup.send(f'Added {newSong.title} by {newSong.artist} to the queue')
        if not guildInfo.voiceClient.is_playing() and not guildInfo.voiceClient.is_paused():
           self.playNext(interaction)


    def playNext(self, interaction):
        guildInfo = self.guilds.get(interaction.guild_id)
        
        nextSong: Song = guildInfo.getSong()
        if nextSong is None:
            prevSong = guildInfo.peekPrevious()
            if prevSong is not None:
                self.getSimilar(prevSong, guildInfo)
            else:
                print("ERROR: No previous song to base rec's on")
                return
            nextSong = guildInfo.getSong()

        if guildInfo.voiceClient.is_playing() or guildInfo.voiceClient.is_paused():
            guildInfo.voiceClient.stop()
        
        nextSong = self.getSongInfo(nextSong)
        FFmpegOptions = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
            'options': '-vn'}
        # guildInfo.voiceClient.play(discord.FFmpegPCMAudio(nextSong.trackUrl, options=FFmpegOptions), after=lambda e: self.playNext(interaction))

        trackEmbed: discord.Embed = self.getNowPlayingEmbed(nextSong)
        if guildInfo.nowPlayingMessage is None:
            run_coroutine_threadsafe(self.initQueueControls(interaction, trackEmbed), interaction.client.loop)
        else:
            run_coroutine_threadsafe(guildInfo.nowPlayingMessage.edit(embed=trackEmbed), interaction.client.loop)

    
    async def initQueueControls(self, interaction: discord.Interaction, embed: discord.Embed) -> None:
        super().__init__(timeout=None)
        self.guilds.get(interaction.guild_id).nowPlayingMessage = await interaction.channel.send(embed=embed, view=self)


    def getSongInfo(self, track: Song) -> Song:
        query = track.artist+' '+track.title
        apiCall = self.spotifyAPI.search(q=query, limit=1, type='track')
        results = apiCall['tracks']['items'][0]

        track.trackID = results['uri']
        images = results['album']['images']
        track.thumbnailURL = images[len(images)-1]['url']
        track.getTrackUrl()
        return track


    def getSimilar(self, track: Song, guildInfo: GuildInfo):     
        trackObj = self.lastFM.get_track(artist=track.artist, title=track.title)
        response = trackObj.get_similar(limit=20)
        for similarItem in response:
            recSong = Song(title=str(similarItem.item.title), artist=str(similarItem.item.artist))
            guildInfo.queueSong(recSong)


    def getNowPlayingEmbed(self, track: Song) -> discord.Embed:
        embed = discord.Embed(
            title='Now Playing',
            description=(f'{track.title} \nby {track.artist}'),
            colour=discord.Color.fuchsia()
        )
        embed.set_thumbnail(url=track.thumbnailURL)
        return embed


