import os
import song
from validators import url
from urllib.parse import urlparse
import re
import pylast
import random
import discord
import spotipy
from sclib import SoundcloudAPI, Track
import asyncio
from groq import Groq
from os import environ
from jokeapi import Jokes
from discord.ext import commands
from musicPlayer import DiscordPlayer
from discord import Message, Intents, app_commands
from spotipy.oauth2 import SpotifyClientCredentials


class MusicBot(commands.Bot):
    def __init__(self):
        intents: Intents = Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix='/', intents=intents)

        # Connection to API's
        self.__jokeAPI: Jokes = asyncio.run(Jokes())
        self.__groq = Groq(api_key=environ.get('GROQ_API_KEY'))
        self.__spotifyAPI = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=environ.get('SPOTIFY_API_KEY'), client_secret=environ.get('SPOTIFY_SECRET_API_KEY')))
        self.__soundcloudAPI = SoundcloudAPI()
        self.__lastFM = pylast.LastFMNetwork(
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


    # Called after the bot is initialized
    async def on_ready(self):
        try:
            self.setup_commands()
            synced = await self.tree.sync()
            await self.change_presence(
                status=discord.Status.online,
                activity=discord.Activity(
                    name='Music',
                    type=discord.ActivityType.listening))       # emoji=discord.PartialEmoji(name='Music').from_str('♫')
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
    

    # Message handler for messages sent to the bot
    async def on_message(self, message: discord.Message) -> None:
        user_message: str = message.content
        if message.author.id == self.user.id or user_message == '':
            # Messages sent from this bot or messages with no text
            return
        elif str(self.user.id) in user_message:
            # Bot was tagged with @bot_username
            tag: str = f'<@{self.user.id}>'
            responseList: list[str] = self.__getAiResponse(prompt=user_message.replace(tag, ''))
            await self.sendStringList(stringList=responseList, message=message, dm=isinstance(message.channel, discord.channel.DMChannel))
        elif isinstance(message.channel, discord.channel.DMChannel):
            # DM's to the bot
            responseList: list[str] = self.__getAiResponse(prompt=user_message)
            await self.sendStringList(stringList=responseList, message=message, dm=True)
    

    async def sendStringList(self, stringList: list[str], message: discord.Message, dm: bool = False) -> None:
        listLen: int = len(stringList)
        if listLen < 1:
            return
        elif listLen > 1:
            for i, textBlock in enumerate(stringList):
                if i == 0 and dm == False:
                    await message.reply(textBlock)
                else:
                    await message.channel.send(textBlock)
        else:
            if dm == True:
                await message.channel.send(stringList[0])
            else:
                await message.reply(stringList[0])


    def __getAiResponse(self, prompt: str) -> list[str]:
        msgList: list[str] = list()
        try:
            response = self.__groq.chat.completions.create(
                messages = [
                    {
                        "role": "user",
                        "content": prompt,
                    }
                ],
                model="llama3-8b-8192",
            )
            msg = response.choices[0].message.content
        except Exception as e:
            msgList.append("Please try again later. (=ʘᆽʘ=)")
            return msgList
        responseLength: int = len(msg)
        if responseLength < 1:
            msgList.append("Something went wrong, please try again.")
            return msgList
        elif len(msg) < 2000:
            msgList.append(msg)
            return msgList
        else:
            textBlock: str = ''
            for i, char in enumerate(msg):
                textBlock += char
                if i == (responseLength-1) or ((i+1) % 2000) == 0:     # Last char
                    msgList.append(textBlock)
                    textBlock = ''
            return msgList


    def __getInputSong(self, query: str, requestor: discord.User) -> song.Song:
        trackInfo: object = None        # JSON API response
        inputSong: song.Song = None
        if url(query):
            print(query)
            domain = urlparse(query).netloc.lower()
            print(domain)
            if domain.endswith('spotify.com'):
                # Works
                try:
                    trackInfo = self.__spotifyAPI.track(track_id=query)
                except Exception as e:
                    return None
                if trackInfo == None:
                    return None
                artistsList: list[str] = list()
                for artist in trackInfo['artists']:
                    artistsList.append(artist['name'])
                inputSong = song.SpotifySong(id=trackInfo['id'], title=trackInfo['name'], artists=artistsList, requestor=requestor, duration=trackInfo['duration_ms'],
                        thumbnailUrl=trackInfo['album']['images'][len(trackInfo['album']['images'])-1]['url'], explicit=trackInfo['explicit'])
            elif domain.endswith('soundcloud.com'):
                print("SoundCloud URL detected")
                try:
                    trackInfo = self.__soundcloudAPI.resolve(query)
                except Exception as e:
                    return None
                assert type(trackInfo) is Track
            elif domain.endswith('music.apple.com'):
                print("Apple Music URL detected")
        elif query[:4] == "FM@#":
            # Works
            try:
                trackInfo = self.__spotifyAPI.search(q=f"{(query.split('@#')[1]).split('^*')[0]} {query.split('^*')[1]}", type=['track'])['tracks']['items'][0]
            except Exception as e:
                return None
            if trackInfo == None:
                return None
            artistsList: list[str] = list()
            for artist in trackInfo['artists']:
                artistsList.append(artist['name'])
            inputSong = song.SpotifySong(id=trackInfo['id'], title=trackInfo['name'], artists=artistsList, requestor=requestor, duration=trackInfo['duration_ms'],
                    thumbnailUrl=trackInfo['album']['images'][len(trackInfo['album']['images'])-1]['url'], explicit=trackInfo['explicit'])
        return inputSong



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
        

        @self.tree.command(name='coinflip', description='Flips a coin')
        async def coinflip(interaction: discord.Interaction):
            value: int = random.randint(0, 1)
            result: str = None
            if value < 1:
                result = 'Heads'
            else:
                result = 'Tails'
            await interaction.response.send_message(f'Coin flip result: {result}')


        async def songSelect(interaction: discord.Interaction, current: str) -> list[app_commands.Choice[str]]:
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
        @app_commands.autocomplete(query=songSelect)
        async def play(interaction: discord.Interaction, query: str):
            await interaction.response.defer()
            if query is None:
                return
            elif not interaction.user.voice:
                await interaction.followup.send('Join a voice channel to play music.')
                return
            
            queuedSong: song.Song = self.__getInputSong(query=query, requestor=interaction.user)
            if queuedSong is None:
                await interaction.followup.send(f'Select a song from search or paste a song link from Spotify, SoundCloud, or Apple Music. Type /help for more info.')
                return
            musicPlayer: DiscordPlayer = self.__guilds.get(interaction.guild_id)
            if musicPlayer is None:
                guildPath: str = os.path.join(self.__binPath, str(interaction.guild_id))
                if not os.path.exists(guildPath):
                    os.makedirs(guildPath)
                self.__guilds.update({interaction.guild_id:DiscordPlayer(guildID=interaction.guild_id, folderPath=guildPath)})
                musicPlayer = self.__guilds.get(interaction.guild_id)
            await musicPlayer.queueSong(song=queuedSong, interaction=interaction)


        @self.tree.command(name='help', description='Overview and usage of the bot.')
        async def help(interaction: discord.Interaction):
            # 1354211336652853461 SoundCloud, or Apple Music
            messageList: list[str] = list()
            helpMessage1: str = ""
            helpMessage2: str = ""
            helpMessage1 += "# DJ Music Bot Overview"
            helpMessage1 += "\n### Commands"
            helpMessage1 += "\n1. </play:1318586886394220637> - The play command allows you to play music in a discord server's voice channel."
            helpMessage1 += "\n  - __Prequisites:__ You must be connected to a voice channel before using the command. The bot must be a member of the server you are attempting to use the command in."
            helpMessage1 += "\n  - __Usage:__ Type '/play' in the message section of a text channel and press enter, you should be prompted with a 'query' box and an options list."
            helpMessage1 += " You can search for a song by typing in the song name or artists name in the 'query' box and choosing a song from the options list."
            helpMessage1 += " Alternatively, you can paste a song link from Spotify into the 'query' box."
            helpMessage1 += " Paste the link and press the right arrow key once to escape the 'query' box, then press enter to execute the command."
            helpMessage1 += "\n  - __Controls:__ After music starts playing, the bot will send a message containing the song info and three buttons to control the song queue."
            helpMessage1 += " First is the rewind button, this will play the previous song. Next is the pause/play button, this button will pause or play the music and edit the message to indicate if the music is paused or playing."
            helpMessage1 += " Last is the skip button to play the next song."
            helpMessage1 += "\n  - __Disconnnecting:__ The bot can be manually disonnected from voice channels by users with permissions(typically server admins or owners), contact the server owner for permissions."
            helpMessage1 += " While the bot is connected to a voice channel, right-click on the bot, look for the button with red text labeled 'Disconnect', and left-click it."
            helpMessage1 += " Alternatively, the bot will automatically leave voice channnels when all other members leave."

            helpMessage2 += "2. </joke:1317067512374100029> - The joke command will send a text message containing a joke in the text channel the command was used in."
            helpMessage2 += "\n  - __Prequisites:__ The command must be used in a text channel; This can either be via DM or in a text channel within a server that the bot is a member of."
            helpMessage2 += "\n  - __Usage:__ In the bottom of a text channel, there is a 'message' section. Type '/joke' and press enter."

            helpMessage2 += "\n\n### Issues"
            helpMessage2 +="\nIf you are still having issues, please join the Support Server for assistance: https://discord.gg/Qb4dU3Wx76"
            

            await interaction.response.send_message(helpMessage1)
            await interaction.channel.send(helpMessage2)

                

