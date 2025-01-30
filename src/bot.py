import os
import re
import pylast
import random
import discord
import spotipy
import asyncio
from os import environ
from jokeapi import Jokes
from discord.ext import commands
from musicPlayer import Song, GuildPlayer
from discord import Message, Intents, app_commands
from spotipy.oauth2 import SpotifyClientCredentials


class MusicBot(commands.Bot):
    def __init__(self):
        intents: Intents = Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix='/', intents=intents)

        # Connection to API's
        self.jokeAPI: Jokes = asyncio.run(Jokes())
        self.spotifyAPI = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=environ.get('SPOTIFY_API_KEY'), client_secret=environ.get('SPOTIFY_SECRET_API_KEY')))
        self.lastFM: LastFMNetwork = pylast.LastFMNetwork(
            api_key=environ.get('LASTFM_API_KEY'),
            api_secret=environ.get('LASTFM_SECRET_API_KEY'),
            username=environ.get('LASTFM_USERNAME'),
            password_hash=(pylast.md5(environ.get('LASTFM_PASSWORD')))
        )

        # Class variables
        self.__guilds: (int, GuildPlayer) = {}
        if not os.path.exists(os.path.join(os.getcwd(), "bin")):
            os.makedirs(os.path.join(os.getcwd(), "bin"))
        self.__binPath: str = os.path.join(os.getcwd(), "bin")


    # Message handler for @ tags in text channels
    async def on_message(self, message: Message):
        author: str = str(message.author)
        user_message: str = message.content

        if author == self.user or not user_message:
            # Checks for messages sent from this bot
            return
        elif str(self.user.id) in user_message:
            print(f'BOT WAS TAGGED:{user_message}')


    # Called after the bot is initialized
    async def on_ready(self):
        try:
            self.setup_commands()
            synced = await self.tree.sync()
            print(f'Logged in as {self.user}')
        except Exception as e:
            print(f'Error syncing commands: {e}')


    # Called when a user updates their voice state inside the same guild the bot is in
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        voice_state = member.guild.voice_client
        if voice_state is None:
            return
        elif len(voice_state.channel.members) == 1:     # Need to be sure the member is self
            guildPlayer = self.__guilds.get(member.guild.id)
            if guildPlayer is None:
                return
            else:
                guildPath: str = guildPlayer.folderPath
                await guildPlayer.disconnect()
                self.__guilds.pop(member.guild.id)
                for fileName in os.listdir(guildPath):
                    filePath = os.path.join(guildPath, fileName)
                    try:
                        if os.path.isfile(filePath) or os.path.islink(filePath):
                            os.unlink(filePath)
                    except Exception as e:
                        print(e)
                print(f'Auto-disconnect complete for guild: {member.guild.name}\n')


    def setup_commands(self):
        @self.tree.command(name='joke', description='Sends a joke in chat. Be Warned: These may be dark humor.')
        async def joke(interaction: discord.Interaction):
            # Blacklist: nsfw, religious, political, racist, sexist
            joke: str = None
            response: dict = await self.jokeAPI.get_joke(category=['misc', 'dark', 'pun'],
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
        

        @self.tree.command(name='coinflip', description='Flips a coin')
        async def coinflip(interaction: discord.Interaction):
            value: int = random.randint(0, 1)
            result: str = None
            if value < 1:
                result = 'Heads'
            else:
                result = 'Tails'
            await interaction.response.send_message(f'Coin flip result: {result}')


        async def search_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
            trackList: [app_commands.Choice] = []
            trackQuery: str = ''

            if current == '':
                apiCall = self.lastFM.get_top_tracks(limit=7)
                for track in apiCall:
                    trackQuery = str(track.item)
                    if len(trackQuery) > 99:
                        trackQuery = trackQuery[0:99]
                    trackList.append(app_commands.Choice(name=trackQuery, value=(f'FM@#{track.item.artist}^*{track.item.title}')))
            else:
                apiCall = self.spotifyAPI.search(q=current, limit=7, type=['track', 'artist'])
                searchResults = apiCall['tracks']['items']

                for item in searchResults:
                    trackQuery = f"{item['artists'][0]['name']} - {item['name']}"
                    if len(trackQuery) > 99:
                        trackQuery = trackQuery[0:99]
                    trackList.append(app_commands.Choice(name=trackQuery, value=(f"SP@#{item['uri']}")))
            return trackList


        @self.tree.command(name='play', description='Plays music in your voice channel')
        @app_commands.describe(query='Song select')
        @app_commands.autocomplete(query=search_autocomplete)
        async def play(interaction: discord.Interaction, query: str):
            await interaction.response.defer()
            if not interaction.user.voice:
                await interaction.followup.send('Join a voice channel to play music')
                return
            
            if re.search(r'.com', query):
                await interaction.followup.send(f'Currently no support for links')
                return
            elif '@#' not in query:
                await interaction.followup.send(f'Song not in database')
                return
            
            trackInfo: object = None
            queuedSong: Song = None
            match query.split('@#')[0]:
                case 'FM':
                    trackSearch = self.spotifyAPI.search(q=f"{(query.split('@#')[1]).split('^*')[0]} {query.split('^*')[1]}", type=['track'])
                    trackInfo = trackSearch['tracks']['items'][0]
                case 'SP':
                    trackInfo = self.spotifyAPI.track(track_id=query.split('@#')[1])
                case _:
                    await interaction.followup.send("Error: Matched base-case\nCongrats, please contact discord user jakester48 with steps to recreate")
                    return

            artistsList: [str] = []
            for artist in trackInfo['artists']:
                artistsList.append(artist['name'])
            queuedSong = Song(id=trackInfo['id'], title=trackInfo['name'], artists=artistsList, requestor=interaction.user, duration=trackInfo['duration_ms'],
                    thumbnailUrl=trackInfo['album']['images'][len(trackInfo['album']['images'])-1]['url'])

            guildPlayer = self.__guilds.get(interaction.guild_id)
            if guildPlayer is None:
                guildPath: str = os.path.join(self.__binPath, str(interaction.guild_id))
                if not os.path.exists(guildPath):
                    os.makedirs(guildPath)
                
                self.__guilds.update({interaction.guild_id:
                    GuildPlayer(guildID=interaction.guild_id, folderPath=guildPath)})
                guildPlayer = self.__guilds.get(interaction.guild_id)
            await guildPlayer.queueSong(song=queuedSong, interaction=interaction)


                
