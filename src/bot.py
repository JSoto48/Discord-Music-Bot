from os import environ
import discord
from discord import Message, Intents, app_commands
from discord.ext import commands
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from musicPlayer import Song, QueueManager
import random
from dadjokes import Dadjoke
import pylast

def getGreeting() -> str:
    greetings: [str] = [
                'Hiya',                                 # Midwestern
                'Howdy',
                'Hey neighbor',
                'Hey sugar',
                'Greetings',                            # Funny
                'Ahoy',
                'Salutations',
                'Ahoy there',
                'Speak of the devil...',
                'What\'s cooking good lookin',
                'So.. we meet at last',
                'Wazzup',
                'Whats good',                           # Slang
                'Yurrrr',
                'Sup g',
                'Slap me some skin, soul brother',      #Racist
                'What it do, baby boo',
                'Hey, my N word',
                'Herro',
                'Hola',                                 # Mexican
                'Aye foo',
                'Sup esse',
                'Órale amigo',
                'Mira güey',
                'Lovely jubly',                         # British
                'Oi oi',
                'You\'re a sight for sore eyes',        # Nice
                'What\'s up, fuckstick',                # Rude
                'Hey asswipe',
                'Didn\'t see ya there, dickbooger',
                'Sup nerd',
                '*sigh* hey',                           # Action based
            ]

    randomGreeting: str = greetings[random.randint(0, len(greetings))]
    return randomGreeting



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
        @self.tree.command(name='hello', description='Greet the bot')
        async def hello(interaction: discord.Interaction):
            await interaction.response.send_message(f'{getGreeting()}, {interaction.user.mention}!')


        @self.tree.command(name='joke', description='Responds with a dad joke')
        async def joke(interaction: discord.Interaction):
            await interaction.response.send_message(Dadjoke().joke)
        

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

            if current == '':
                apiCall = self.lastFM.get_top_tracks(limit=7)
                for track in apiCall:
                    tempTitle = str(track.item.title)
                    tempArtist = str(track.item.artist)
                    trackList.append(app_commands.Choice(name=(tempArtist+' - '+tempTitle), value=(tempArtist+"@#"+tempTitle)))
            else:
                apiCall = self.spotifyAPI.search(q=current, limit=7, type=['track', 'artist'])
                searchResults = apiCall['tracks']['items']

                for index, item in enumerate(searchResults):
                    artist = item['artists'][0]['name']         # BUG(not mine tho) ALL artist data is wrapped in 'extenal_urls' at index 0 
                    title = item['name']
                    trackQuery = artist + " - " + title
                    trackList.append(app_commands.Choice(name=(artist+" - "+title), value=(artist+"@#"+title)))
            return trackList


        @self.tree.command(name='play', description='Plays music in your voice channel')
        @app_commands.describe(query='Song select')
        @app_commands.autocomplete(query=search_autocomplete)
        async def play(interaction: discord.Interaction, query: str):
            await interaction.response.defer()

            if '@#' not in query:
                # Try another search?
                await interaction.followup.send(f'Could not find song')
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

