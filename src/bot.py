from os import environ
import discord
from discord import Message, Intents, app_commands
from discord.ext import commands
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from musicPlayer import Song, QueueManager
import random
from dadjokes import Dadjoke


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
                "Aye foo",
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

    randomGreeting = greetings[random.randint(0, len(greetings))]
    return randomGreeting



class MusicBot(commands.Bot):
    def __init__(self):
        # Initialize the superclass discord.ext.commands.Bot
        intents: Intents = Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='/', intents=intents)

        # Connection to Spotify Python API
        self.spotifyAPI = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=environ.get('SPOTIFY_API_KEY'), client_secret=environ.get('SPOTIFY_SECRET_API_KEY')))

        # Class variables
        self.GUILD = discord.Object(id='1316505478196629585')   # Discord development server GUILD id
        self.queueManager: QueueManager = QueueManager(self)


    def setup_commands(self):
        @self.tree.command(name='hello', description='Greet the bot')
        async def hello(interaction: discord.Interaction):
            await interaction.response.send_message(f"{getGreeting()}, {interaction.user.mention}!")


        @self.tree.command(name='joke', description='Responds with a dad joke')
        async def joke(interaction: discord.Interaction):
            await interaction.response.send_message(Dadjoke().joke)
        

        @self.tree.command(name='coinflip', description='Flips a coin')
        async def coinflip(interaction: discord.Interaction):
            value = random.randint(0, 1)
            result: str = None
            if value < 1:
                result = 'Heads'
            else:
                result = 'Tails'
            await interaction.response.send_message(f'Coin flip result: {result}')


        async def search_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
            # Autofill used for /play command's song select
            # Using Spotify web API to ensure the song exists in their DB
            apiCall = None
            if current == '':
                apiCall = self.spotifyAPI.search(q='test', limit=7, type=['track', 'artist'])
            else:
                apiCall = self.spotifyAPI.search(q=current, limit=7, type=['track', 'artist'])
            searchResults = apiCall['tracks']['items']
            trackSelection = []

            for index, item in enumerate(searchResults):
                artist = item['artists'][0]['name']         # BUG(not mine tho) ALL artist data is wrapped in 'extenal_urls' at index 0 
                track = item['name']
                trackQuery = artist + " - " + track
                trackSelection.append(app_commands.Choice(name=(artist+" - "+track), value=(artist+"@#"+track)))

            return trackSelection


        # -------------TESTING-------------
        @self.tree.command(name='play', description='Plays music in your voice channel', guild=self.GUILD)
        @app_commands.describe(query="Song select")
        @app_commands.autocomplete(query=search_autocomplete)
        async def play(interaction: discord.Interaction, query: str):
            if '@#' not in query:
                await interaction.response.send_message(f'Could not find song')
                return
            
            artist: str = query.split('@#')[0]
            title: str = query.split('@#')[1]
            currentTrack: Song = Song(title=title, artist=artist)

            if not currentTrack.downloadTrack():
                await interaction.response.send_message(f'Error downloading track')
                return

            responseStr = await self.queueManager.play(track=currentTrack, interaction=interaction)
            print(responseStr)



    async def on_ready(self):
        try:
            self.setup_commands()
            synced = await self.tree.sync(guild=self.GUILD)
            print(f'Synced {len(synced)} commands to guild {self.GUILD.id}')
            print('Bot Ready!')
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

