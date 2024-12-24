import yt_dlp as youtube_dl
import discord
from discord.ext import commands
from asyncio import run_coroutine_threadsafe


class Song():
    def __init__(self, title: str = None, artist: str = None):
        self.title: str = title
        self.artist: str = artist
        self.trackUrl: str = None
        self.trackID: str = None
        self.thumbnailURL: str = None
        self.ytdl_opts = {
            'format': 'bestaudio/best',         # Get the best audio quality
            'noplaylist': True,                 # Don't download playlists
            'quiet': True,                      # Show progress
            'default_search': 'ytsearch1',      # Limit search to the first result
            'no_warnings': True,                # Suppress warnings
        }


    def getTrackUrl(self) -> bool:
        query = f'{self.artist} {self.title}'

        with youtube_dl.YoutubeDL(self.ytdl_opts) as ytdl:
            trackInfo = ytdl.extract_info(query, download=False)
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
        self.length += 1
        self.__queue.append(track)

    def pop(self) -> Song:
        # Removes and returns song from the first index of the queue
        self.length -= 1
        return self.__queue.pop(0)

    def peek(self) -> Song:
        # Returns first song without removing it
        firstSong = self.__queue.pop(0)
        self.__queue.insert(0, firstSong)
        return firstSong
    
    def clear(self) -> None:
        self.length = 0
        self.__queue.clear()



class QueueManager():
    def __init__(self, spotifyAPI, lastFM):
        self.musicQueues: (int, [SongQueue, SongQueue]) = {}  # KEY: guildID | VALUE: list[0]=song queue, list[1]=recommended song queue
        self.voiceClients: (int, discord.VoiceClient) = {}
        #self.queueControls = None
        self.nowPlayingMessage = None
        self.lastSong: Song = None

        self.spotifyAPI = spotifyAPI
        self.lastFM = lastFM
        self.FFmpegOptions = {
            'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5', 
            'options': '-vn'}


    async def addToQueue(self, songName: str, songArtist:str, interaction: discord.Interaction):
        interactionGuild: int = interaction.guild_id                # Guild = discord server
        userVoice: discord.VoiceState = interaction.user.voice

        if not userVoice:
            await interaction.followup.send('Join a voice channel to play music')
            return
        newSong: Song = Song(title=songName, artist=songArtist)
        matchingClient: discord.VoiceClient = self.voiceClients.get(interactionGuild)

        if matchingClient is None or not matchingClient.is_connected():
            # Bot is not in voice channel
            # self.clear(interaction)
            newSong.getTrackUrl()
            try:
                newVoiceClient: discord.VoiceClient = await userVoice.channel.connect()
            except Exception as e:
                await interaction.followup.send(f'Failed to connect to voice: {e}')
                
            await interaction.followup.send(f'Added {newSong.title} by {newSong.artist} to the queue')
            await self.play(newSong, interaction, newVoiceClient)
        else:
            # Bot is in voice channel
            self.musicQueues.get(interactionGuild)[0].addSong(newSong, requestor=interaction.user.name)
            if matchingClient.is_playing() or matchingClient.is_paused():
                await interaction.followup.send(f'Added {newSong.title} by {newSong.artist} to the queue')
            else:
                await interaction.followup.send(f'Added {newSong.title} by {newSong.artist} to the queue')
                self.playNext(interaction)


    def playNext(self, interaction) -> discord.Embed:
        guildID = interaction.guild_id
        songQueue: SongQueue = self.musicQueues.get(guildID)[0]
        currentTrack: Song = None

        if songQueue.length > 0:
            # Songs added by users
            currentTrack = songQueue.pop()
            self.lastSong = currentTrack
        else:
            recQueue: SongQueue = self.musicQueues.get(guildID)[1]
            if self.lastSong is not None:
                # Get recommended songs based on the last song queued by users
                self.getSimilar(self.lastSong, guildID=guildID)
                self.lastSong = None
                currentTrack = recQueue.pop()
            elif recQueue.length > 0:
                # Keep playing recommeneded songs added by bot
                currentTrack = recQueue.pop()

        currentVC: discord.VoiceClient = self.voiceClients.get(guildID)
        if currentVC.is_playing() or currentVC.is_paused():
            currentVC.stop()
        
        currentTrack = self.getSongInfo(currentTrack)
        currentVC.play(discord.FFmpegPCMAudio(currentTrack.trackUrl, options=self.FFmpegOptions), after=lambda e: self.playNext(interaction))

        trackEmbed: discord.Embed = self.getNowPlayingEmbed(currentTrack)
        if self.nowPlayingMessage is not None:
            run_coroutine_threadsafe(self.nowPlayingMessage.edit(embed=trackEmbed), interaction.client.loop)
        else:
            return trackEmbed

    
    async def play(self, track: Song, interaction: discord.Interaction, newVoiceClient: discord.VoiceClient):
        guildID = interaction.guild_id
        self.voiceClients[guildID] = newVoiceClient
        self.musicQueues[guildID] = [SongQueue(), SongQueue()]
        self.musicQueues.get(guildID)[0].addSong(track)
        self.nowPlayingMessage = await interaction.channel.send(
            embed=self.playNext(interaction),
            view=QueueControls(queueManager=self, voiceClient=self.voiceClients.get(guildID)))


    def clear(self, interaction):
        guildID = interaction.guild_id
        musicQueues = self.musicQueues.get(guildID)
        for queue in musicQueues:
            if queue.length > 0:
                queue.clear()
    
        if self.nowPlayingMessage is not None:
            self.nowPlayingMessage.clear()
            self.nowPlayingMessage = None


    def getSongInfo(self, track: Song) -> Song:
        track.getTrackUrl()
        query = track.artist+' '+track.title
        apiCall = self.spotifyAPI.search(q=query, limit=1, type='track')
        results = apiCall['tracks']['items'][0]

        track.trackID = results['uri']
        images = results['album']['images']
        track.thumbnailURL = images[len(images)-1]['url']
        return track


    def getSimilar(self, track: Song, guildID: int):
        # Based on listening data, adds similar tracks to the guildID's recommended queue
        recQueue = self.musicQueues.get(guildID)[1]
        if recQueue.length > 0:
            recQueue.clear()
        
        trackObj = self.lastFM.get_track(artist=track.artist, title=track.title)
        response = trackObj.get_similar(limit=20)
        for similarItem in response:
            recSong = Song(title=str(similarItem.item.title), artist=str(similarItem.item.artist))
            recQueue.addSong(track=recSong)


    def getNowPlayingEmbed(self, track: Song) -> discord.Embed:
        embed = discord.Embed(
            title='Now Playing',
            description=(f'{track.title} \nby {track.artist}'),
            colour=discord.Color.fuchsia()
        )
        embed.set_thumbnail(url=track.thumbnailURL)
        return embed

    def getPausedEmbed(self) -> discord.Embed:
        embed = discord.Embed(
            title='Pasued',
            colour=discord.Color.fuchsia()
        )
        return embed


class QueueControls(discord.ui.View):
    def __init__(self, queueManager: QueueManager, voiceClient: discord.VoiceClient):
        super().__init__(timeout=None)
        self.queueManager = queueManager
        self.voiceClient = voiceClient


    @discord.ui.button(emoji='⏯', style=discord.ButtonStyle.grey)
    async def pause(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.voiceClient.is_paused():
            self.voiceClient.resume()
        elif self.voiceClient.is_playing():
            self.voiceClient.pause()
            await interaction.message.edit(embed=self.queueManager.getPausedEmbed())


    @discord.ui.button(emoji='⏭', style=discord.ButtonStyle.grey)
    async def skip(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        trackEmbed = self.queueManager.playNext(interaction)

