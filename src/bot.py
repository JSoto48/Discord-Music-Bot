from os import environ
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import discord
from discord import Client, Message, Intents, app_commands
from discord.ext import commands
import random


class MusicBot(commands.Bot):
    # Initializes the Discord client and Spotify API 
    def __init__(self):
        intents: Intents = Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='/', intents=intents)
        #self.commandTree = self.tree
        self.spotifyApi = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=environ.get('SPOTIFY_API_KEY'), client_secret='SPOTIFY_SECRET_API_KEY'))
        self.GUILD = discord.Object(id='1316505478196629585')
    

    def setup_commands(self):
        # Initialize the command tree with the following commands:
        @self.tree.command(name='hello', description='Say hello to the bot', guild=self.GUILD)
        async def hello(interaction: discord.Interaction):
            greetings = [
                'Hiya',
                'Howdy',
                'Hey neighbor',
                'Hey sugar',
                'Salutations',
                'Ahoy there',
                'Speak of the devil...',
                'What\'s cooking good lookin'
            ]
            randomGreeting = greetings[random.randint(0, len(greetings))]
            await interaction.response.send_message(f"{randomGreeting}, {interaction.user}!")

    
    async def on_ready(self):
        try:
            self.setup_commands()
            synced = await self.tree.sync(guild=self.GUILD)
            print(f'Synced {len(synced)} commands to guild {self.GUILD.id}')
        except Exception as e:
            print(f'Error syncing commands: {e}')

        if self.spotifyApi:
            print("Spotify API initialized successfully!")
            print(f'Discord bot {self.user} is ready for commands!')
        else:
            print("ERROR: Spotify API failed to initialize.")
            print(f'Discord bot {self.user} failed to initialize.')
            exit(1)

        

    # Message Handler
    async def on_message(self, message: Message):
        channel: str = str(message.channel)
        author: str = str(message.author)
        user_message: str = message.content
        print(f'intercepted message: {channel} {author}: "{user_message}"')

        if author == self.user or not user_message:
            return
        # elif self.user in user_message:
        #     print(f'BOT WAS TAGGED:{user_message}')

        