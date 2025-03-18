import os
import re
import pylast
import random
import discord
import spotipy
import asyncio
from groq import Groq
from os import environ
from jokeapi import Jokes
from discord.ext import commands
from musicPlayer import Song, DiscordPlayer
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
        self.groq = Groq(api_key=environ.get('GROQ_API_KEY'))
        self.spotifyAPI = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=environ.get('SPOTIFY_API_KEY'), client_secret=environ.get('SPOTIFY_SECRET_API_KEY')))
        self.lastFM = pylast.LastFMNetwork(
            api_key=environ.get('LASTFM_API_KEY'),
            api_secret=environ.get('LASTFM_SECRET_API_KEY'),
            username=environ.get('LASTFM_USERNAME'),
            password_hash=(pylast.md5(environ.get('LASTFM_PASSWORD')))
        )

        # Class variables
        if not os.path.exists(os.path.join(os.getcwd(), "bin")):
            os.makedirs(os.path.join(os.getcwd(), "bin"))           # Ensure R/W permissions
        self.__binPath: str = os.path.join(os.getcwd(), "bin")
        self.__guilds: dict[int, DiscordPlayer] = {}

    # Message handler for @ tags in text channels
    async def on_message(self, message: discord.Message):
        user_message: str = message.content
        aiReply: str = ''

        if message.author.id == self.user.id or user_message == '':
            # Messages sent from this bot or messages with no text
            return
        elif isinstance(message.channel, discord.channel.DMChannel):
            # DM's to the bot
            aiReply = self.getAiResponse(prompt=user_message)
        elif str(self.user.id) in user_message:
            # Bot was tagged with @bot_username
            tag: str = f'<@{self.user.id}>'
            prompt = user_message.replace(tag, '')
            aiReply = self.getAiResponse(prompt=prompt)
        
        if len(aiReply) >= 2000:
            aiReply = aiReply[0:1999]
        await message.reply(aiReply)


    # Called after the bot is initialized
    async def on_ready(self):
        try:
            self.setup_commands()
            synced = await self.tree.sync()
            await self.change_presence(status=discord.Status.online, activity=discord.)
            print(f'Logged in as {self.user}. Commands in tree: {len(synced)}.')
        except Exception as e:
            print(f'Error syncing commands: {e}')

    # Called when a user updates their voice state(joins, leaves, mutes...) inside the same guild the bot is in
    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        musicPlayer = self.__guilds.get(member.guild.id)
        if musicPlayer is None:
            return
        elif musicPlayer.getChannelLength() == 1:
            # If bot is alone in VC or someone kicked the bot from VC
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
            

    # Used for when bot is tagged
    def getAiResponse(self, prompt: str) -> str:
        try:
            response = self.groq.chat.completions.create(
                messages = [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="llama3-8b-8192",
            )
            return response.choices[0].message.content
        except Exception as e:
            return "Please try again later. (=ʘᆽʘ=)"

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
            await interaction.response.defer()
            trackList: list[app_commands.Choice] = list()
            trackQuery: str = ''
            apiCall = None

            if current == '':
                apiCall = self.lastFM.get_top_tracks(limit=7)
                for track in apiCall:
                    trackQuery = str(track.item)
                    trackValue: str = f'FM@#{track.item.artist}^*{track.item.title}'
                    if len(trackQuery) > 99:
                        trackQuery = trackQuery[0:99]
                    if len(trackValue) > 99:
                        trackValue = trackValue[0:99]
                    trackList.append(app_commands.Choice(name=trackQuery, value=trackValue))
            else:
                apiCall = self.spotifyAPI.search(q=current, limit=7, type=['track', 'artist'])
                searchResults = apiCall['tracks']['items']

                for item in searchResults:
                    trackQuery = f"{item['artists'][0]['name']} - {item['name']}"
                    if len(trackQuery) > 99:
                        trackQuery = trackQuery[0:99]
                    trackList.append(app_commands.Choice(name=trackQuery, value=(f"SP@#{item['uri']}")))
            return trackList


        @self.tree.command(name='play', description='Plays music in your voice channel.')
        @app_commands.describe(query='Song select')
        @app_commands.autocomplete(query=search_autocomplete)
        async def play(interaction: discord.Interaction, query: str):
            await interaction.response.defer()
            if not interaction.user.voice:
                await interaction.followup.send('Join a voice channel to play music.')
                return
            
            if re.search(r'.com', query):
                await interaction.followup.send(f'No current support for links.')
                return
            elif '@#' not in query:
                await interaction.followup.send(f'Song not found from list.')
                return
            
            trackInfo: object = None        # JSON API response
            match query.split('@#')[0]:
                case 'FM':
                    trackSearch = self.spotifyAPI.search(q=f"{(query.split('@#')[1]).split('^*')[0]} {query.split('^*')[1]}", type=['track'])
                    trackInfo = trackSearch['tracks']['items'][0]
                case 'SP':
                    trackInfo = self.spotifyAPI.track(track_id=query.split('@#')[1])
                case _:
                    await interaction.followup.send("Error: How tf did u even get this error?")
                    return

            artistsList: list[str] = list()
            for artist in trackInfo['artists']:
                artistsList.append(artist['name'])

            queuedSong: Song = Song(id=trackInfo['id'], title=trackInfo['name'], artists=artistsList, requestor=interaction.user, duration=trackInfo['duration_ms'],
                    thumbnailUrl=trackInfo['album']['images'][len(trackInfo['album']['images'])-1]['url'])

            musicPlayer = self.__guilds.get(interaction.guild_id)
            if musicPlayer is None:
                guildPath: str = os.path.join(self.__binPath, str(interaction.guild_id))
                if not os.path.exists(guildPath):
                    os.makedirs(guildPath)
                self.__guilds.update({interaction.guild_id:DiscordPlayer(guildID=interaction.guild_id, folderPath=guildPath)})
                musicPlayer = self.__guilds.get(interaction.guild_id)
            await musicPlayer.queueSong(song=queuedSong, interaction=interaction)


                
