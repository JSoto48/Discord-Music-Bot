from os import environ
import discord
from discord import Message, Intents, app_commands
from discord.ext import commands
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from musicPlayer import Song, QueueManager
import random
import dadjokes
import pylast
import re



class MusicBot(commands.Bot):
    def __init__(self):
        # Initialize the superclass discord.ext.commands.Bot
        intents: Intents = Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='/', intents=intents)

        # Connection to Spotify Python API
        self.spotifyAPI = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=environ.get('SPOTIFY_API_KEY'), client_secret=environ.get('SPOTIFY_SECRET_API_KEY')))
        self.lastFM = pylast.LastFMNetwork(
            api_key=environ.get('LASTFM_API_KEY'),
            api_secret=environ.get('LASTFM_SECRET_API_KEY'),
            username=environ.get('LASTFM_USERNAME'),
            password_hash=(pylast.md5(environ.get('LASTFM_PASSWORD')))
        )

        # Class variables
        self.GUILD = discord.Object(id=environ.get('DISCORD_GUILD_ID'))   # Discord development server GUILD id
        self.queueManager: QueueManager = QueueManager(self.spotifyAPI, self.lastFM)


    def setup_commands(self):
        @self.tree.command(name='joke', description='Responds with a dad joke')
        async def joke(interaction: discord.Interaction):
            await interaction.response.send_message(dadjoke.joke())
        

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
            # Autofill used for /play command's song select
            # LastFM API for top tracks, Spotify API for search
            trackList: [app_commands.Choice] = []
            artist: str = ''
            title: str = ''
            trackQuery: str = ''

            if current == '':
                apiCall = self.lastFM.get_top_tracks(limit=7)
                for track in apiCall:
                    title = str(track.item.title)
                    artist = str(track.item.artist)
                    trackList.append(app_commands.Choice(name=(f'{artist} - {title}'), value=(artist+"@#"+title)))
            else:
                apiCall = self.spotifyAPI.search(q=current, limit=7, type=['track', 'artist'])
                searchResults = apiCall['tracks']['items']

                for index, item in enumerate(searchResults):
                    artist = item['artists'][0]['name']         # BUG(not mine tho) ALL artist data is wrapped in 'extenal_urls' at index 0 
                    title = item['name']
                    trackID: str = item['id']
                    if item['explicit']:
                        trackQuery = f'{artist} - {title} (Explicit)'
                    else:
                        trackQuery = f'{artist} - {title}'
                    trackList.append(app_commands.Choice(name=(trackQuery), value=(trackID)))
            return trackList


        @self.tree.command(name='play', description='Plays music in your voice channel')
        @app_commands.describe(query='Song select')
        @app_commands.autocomplete(query=search_autocomplete)
        async def play(interaction: discord.Interaction, query: str):
            await interaction.response.defer()

            url = re.search(r'.com', query)
            if url:
                await interaction.followup.send(f'Currently no support for links')
            elif '@#' not in query:
                await interaction.followup.send(f'Song not in database')
                return
            
            artist: str = query.split('@#')[0]
            title: str = query.split('@#')[1]
            await self.queueManager.addToQueue(songName=title, songArtist=artist, interaction=interaction)


    async def on_ready(self):
        try:
            self.setup_commands()
            synced = await self.tree.sync(guild=self.GUILD)
            print(f'Logged in as {self.user}')
        except Exception as e:
            print(f'Error syncing commands: {e}')


    async def on_disconnect(self):
        print("DISCONNECTED!!!!!!!!!")


    # Message handler for @ tags in text channels
    async def on_message(self, message: Message):
        channel: str = str(message.channel)
        author: str = str(message.author)
        user_message: str = message.content

        if author == self.user or not user_message:
            # Checks for messages sent from this bot
            return
        elif str(self.user.id) in user_message:
            print(f'BOT WAS TAGGED:{user_message}')

