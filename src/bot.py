"""Contains the bot's commands"""
import os
from os import environ
from song import Song, SpotifySong, SoundcloudSong
import pylast
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from sclib import SoundcloudAPI, Track
from musicPlayer import DiscordPlayer
from jokeapi import Jokes

from validators import url
from urllib.parse import urlparse
import asyncio
import discord
from discord.ext import commands
from discord import Intents, app_commands
from embeds import getHelpEmbed


class MusicBot(commands.Bot):
    def __init__(self):
        intents: Intents = Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix='/', intents=intents)

        # API Connections
        self.__jokeAPI: Jokes = asyncio.run(Jokes())
        self.__spotifyAPI = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=environ.get('SPOTIFY_API_KEY'), client_secret=environ.get('SPOTIFY_SECRET_API_KEY')))
        self.__soundcloudAPI = SoundcloudAPI(client_id=environ.get('SOUNDCLOUD_CLIENT_ID'))
        self.__lastFM = pylast.LastFMNetwork(
            api_key=environ.get('LASTFM_API_KEY'),
            api_secret=environ.get('LASTFM_SECRET_API_KEY'),
            username=environ.get('LASTFM_USERNAME'),
            password_hash=(pylast.md5(environ.get('LASTFM_PASSWORD')))
        )

        # Class variables
        if not os.path.exists(os.path.join(os.getcwd(), "bin")):
            os.makedirs(os.path.join(os.getcwd(), "bin"))
        self.__binPath: str = os.path.join(os.getcwd(), "bin")
        self.__guilds: dict[int, DiscordPlayer] = dict()


    # Called after the bot is finished initializing
    async def on_ready(self):
        try:
            await self.load_extension(name='messenger')
            self.setup_commands()
            synced = await self.tree.sync()
            await self.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(
                    name='Music',
                    type=discord.ActivityType.playing))
            print(f'Logged in as {self.user}. Commands in tree: {len(synced)}.')
        except Exception as e:
            print(f'Error syncing commands: {e}')


    # Voice Channel Auto-Disconnect Handler
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        musicPlayer = self.__guilds.get(member.guild.id)
        if musicPlayer is None:
            return
        elif musicPlayer.getChannelLength() == 1:
            # Bot is alone in the Voice Channel
            musicPlayer.disconnecting = True
            guildPath: str = musicPlayer.folderPath
            await musicPlayer.disconnect()
            for fileName in os.listdir(guildPath):
                filePath = os.path.join(guildPath, fileName)
                try:
                    if os.path.isfile(filePath) or os.path.islink(filePath):
                        os.unlink(filePath)
                except Exception as e:
                    print(e)
            self.__guilds.pop(member.guild.id)
            print(f'Auto-disconnect complete for guild: {member.guild.name}\n')
        elif member == self.user and after.channel is None:
            # Bot was manually disconnected from the Voice Channel
            if musicPlayer.disconnecting:
                return
            musicPlayer.disconnecting = True
            guildPath: str = musicPlayer.folderPath
            await musicPlayer.disconnect()
            for fileName in os.listdir(guildPath):
                filePath = os.path.join(guildPath, fileName)
                try:
                    if os.path.isfile(filePath) or os.path.islink(filePath):
                        os.unlink(filePath)
                except Exception as e:
                    print(e)
            self.__guilds.pop(member.guild.id)
            print(f'Auto-disconnect complete for guild: {member.guild.name}\n')
    

    def __getInputSong(self, query: str, requestor: discord.User, path: str) -> Song:
        trackInfo: object = None        # JSON API response
        if url(query):
            domain = urlparse(query).netloc.lower()
            if domain.endswith('spotify.com'):
                try:
                    trackInfo = self.__spotifyAPI.track(track_id=query)
                except:
                    return None
                if trackInfo is None:
                    return None
                artistsList: list[str] = list()
                for artist in trackInfo['artists']:
                    artistsList.append(artist['name'])
                return SpotifySong(id=trackInfo['id'], title=trackInfo['name'], artists=artistsList, requestor=requestor, guildFolderPath=path,
                                        duration=trackInfo['duration_ms'], thumbnailUrl=trackInfo['album']['images'][len(trackInfo['album']['images'])-1]['url'], explicit=trackInfo['explicit'])
            elif domain.endswith('soundcloud.com'):
                try:
                    trackInfo = self.__soundcloudAPI.resolve(query)
                except:
                    return None
                if type(trackInfo) is Track:
                    try:
                        trackStream: str = trackInfo.get_stream_url()
                    except Exception as e:
                        print(e)
                        #TODO: check if streamable, if downloadable, otherwise YTDL
                        return None
                    if trackStream is None:
                        return None
                    return SoundcloudSong(id=trackInfo.id, title=trackInfo.title, artists=[trackInfo.artist], requestor=requestor,
                                                streamURL=trackStream, duration=trackInfo.duration, thumbnailUrl=trackInfo.artwork_url)
                else:
                    return None
        elif query[:4] == "FM@#":
            try:
                trackInfo = self.__spotifyAPI.search(q=f"{(query.split('@#')[1]).split('^*')[0]} {query.split('^*')[1]}", type=['track'])['tracks']['items'][0]
            except Exception as e:
                return None
            if trackInfo == None:
                return None
            artistsList: list[str] = list()
            for artist in trackInfo['artists']:
                artistsList.append(artist['name'])
            return SpotifySong(id=trackInfo['id'], title=trackInfo['name'], artists=artistsList, requestor=requestor, guildFolderPath=path,
                               duration=trackInfo['duration_ms'], thumbnailUrl=trackInfo['album']['images'][len(trackInfo['album']['images'])-1]['url'], explicit=trackInfo['explicit'])


    def setup_commands(self):
        @self.tree.command(name='joke', description='Sends a joke in chat. Be Warned: These may be dark humor.')
        async def joke(interaction: discord.Interaction):
            # Blacklist: nsfw, religious, political, racist, sexist
            joke: str = None
            response: dict = await self.__jokeAPI.get_joke(category=['misc', 'dark', 'pun'],
                            response_format='json',
                            joke_type='Any',
                            search_string=None,
                            amount=1,
                            lang='en')
            match response['type']:
                case 'single':
                    joke = str(response['joke'])
                case 'twopart':
                    joke = f"{response['setup']}\n{response['delivery']}"
                case _:
                    joke = 'Your life'
            await interaction.response.send_message(joke)
        

        async def __songSelect(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
            await interaction.response.defer()
            trackList: list[app_commands.Choice] = list()
            trackQuery: str = ''
            apiCall = None

            if current == '':
                apiCall = self.__lastFM.get_top_tracks(limit=7)
                for track in apiCall:
                    trackQuery = str(track.item)
                    trackValue: str = f'FM@#{track.item.artist}^*{track.item.title}'
                    if len(trackQuery) > 99:
                        trackQuery = trackQuery[0:98]
                    if len(trackValue) > 99:
                        trackValue = trackValue[0:98]
                    trackList.append(app_commands.Choice(name=trackQuery, value=trackValue))
            elif url(current):
                return trackList
            else:
                apiCall = self.__spotifyAPI.search(q=current, limit=7, type=['track', 'artist'])
                searchResults = apiCall['tracks']['items']

                for item in searchResults:
                    trackQuery = f"{item['artists'][0]['name']} - {item['name']}"
                    if len(trackQuery) > 99:
                        trackQuery = trackQuery[0:98]
                    trackList.append(app_commands.Choice(name=trackQuery, value=item['external_urls']['spotify']))    # TODO: value = the  'external_urls' 'spotify' -> string
            return trackList


        @self.tree.command(name='play', description='Plays music in your voice channel.')
        @app_commands.describe(query='Song select')
        @app_commands.autocomplete(query=__songSelect)
        async def play(interaction: discord.Interaction, query: str):
            await interaction.response.defer()
            if query is None:
                return
            elif not interaction.user.voice:
                await interaction.followup.send('Join a voice channel to play music.')
                return
            
            guildPath: str = os.path.join(self.__binPath, str(interaction.guild_id))
            queuedSong: Song = self.__getInputSong(query=query, requestor=interaction.user, path=guildPath)
            if queuedSong is None:
                await interaction.followup.send(f'Select a song from search or paste a song link from Spotify, SoundCloud, or Apple Music. Type /help for more info.')
                return
            musicPlayer: DiscordPlayer = self.__guilds.get(interaction.guild_id)
            if musicPlayer is None:
                if not os.path.exists(guildPath):
                    os.makedirs(guildPath)
                self.__guilds.update({interaction.guild_id:DiscordPlayer(guildID=interaction.guild_id, folderPath=guildPath)})
                musicPlayer = self.__guilds.get(interaction.guild_id)
            await musicPlayer.queueSong(song=queuedSong, interaction=interaction)


        @self.tree.command(name='help', description='Overview and usage of the bot.')
        async def help(interaction: discord.Interaction):
            await interaction.response.send_message(embed=getHelpEmbed())

                

