from os import environ
import discord
from discord import Message, Intents, app_commands
from discord.ext import commands
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from song import Song


import random
from dadjokes import Dadjoke





class MusicBot(commands.Bot):
    def __init__(self):
        intents: Intents = Intents.default()
        intents.message_content = True
        super().__init__(command_prefix='/', intents=intents)       # Initialize the superclass discord.ext.commands.Bot

        # Connection to Spotify Python API
        self.spotifyAPI = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=environ.get('SPOTIFY_API_KEY'), client_secret=environ.get('SPOTIFY_SECRET_API_KEY')))

        # Class variables
        self.GUILD = discord.Object(id='1316505478196629585')   # Discord development server GUILD id
        self.songQueue: [] = None                               # FIFO queue
        self.isPlaying = False
    


    def setup_commands(self):
        # Initialize the command tree with the following commands:
        # Command 1: Greetings
        @self.tree.command(name='hello', description='Greet the bot')
        async def hello(interaction: discord.Interaction):
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
            await interaction.response.send_message(f"{randomGreeting}, {interaction.user.mention}!")


       # Command 2: Dad Joke
        @self.tree.command(name='joke', description='Responds with a dad joke')
        async def joke(interaction: discord.Interaction):
            await interaction.response.send_message(Dadjoke().joke)


        async def search_autocomplete(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
            # Using Spotify web API to ensure the song exists
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
     

        # Command 3: Play Song
        @self.tree.command(name='play', description='Plays music in your voice channel', guild=self.GUILD)
        @app_commands.describe(query="Song select")
        @app_commands.autocomplete(query=search_autocomplete)
        async def play(interaction: discord.Interaction, query: str):
            artist = query.split('@#')[0]
            title = query.split('@#')[1]
            currentTrack = Song(title=title, artist=artist)
            currentTrack.downloadTrack()
            print('in play')
            
            await interaction.response.send_message(f'here')


            # Step 3: Connect bot to Discord voice channel
            # if interaction.user.voice:
            #     voiceChannel = interaction.user.voice.channel   # Bot will only connect if user is in voice channel
            #     try:
            #         await voiceChannel.connect()
            #         await interaction.response.send_message(f'Playing song: {title}')
            #     except Exception as e:
            #         print(f'Error connecting to voice channel: {e}')
            # else:
            #     # self.songQueue.append(song)
            #     # if self.isPlaying: idk yet
            #     # await interaction.response.send_message('Join a voice channel to play music')   # BUG!
            #     await interaction.response.send_message(f'Song selected = {title}')

            # Step 4: Play song from matching API
                # Prioritize by search match
                    # Then by stream quality
                    

            # ytSearch = Search(query=(artist+' '+title+' audio'))         # pytube.Search
            
            # ytTrack = ytSearch.results[0]
            # # for i, ytObject in enumerate(ytSearch.results):
            # #     print(f'{i} - {ytObject.title} URL: {ytObject.watch_url}')
            # # print("---------------------------------")
            # # print(ytTrack.watch_url)
            # yt = YouTube(ytTrack.watch_url)
            # #print(yt.streams)
            # yt.streams.download(output_path=DOWNLOAD_FOLDER)



    async def on_ready(self):
        try:
            self.setup_commands()
            synced = await self.tree.sync(guild=self.GUILD)
            print(f'Synced {len(synced)} commands to guild {self.GUILD.id}')
        except Exception as e:
            print(f'Error syncing commands: {e}')

        if self.spotifyAPI:
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
        elif str(self.user.id) in user_message:
            print(f'BOT WAS TAGGED:{user_message}')

