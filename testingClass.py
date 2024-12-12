import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

from discord import Intents, Client
from discord.ext import commands



from dotenv import load_dotenv
from os import environ


class SpotifyAPI():
    def __init__(self):
        load_dotenv()
        self.spotify = spotipy.Spotify(auth_manager=SpotifyClientCredentials(client_id=environ.get('SPOTIFY_API_KEY'), client_secret='SPOTIFY_SECRET_API_KEY'))
        
    
    def confirm(self) -> bool:
        if self.spotify:
            return True
        else:
            return False



# class SpotifyCommands(commands.Bot):
    #async def on_ready(self):
     #   print(f'Discord bot {self.user} is ready for commands!')



     # Bot Setup
#client: Client = Client(intents=intents)
#spotifyBot: SpotifyBot = SpotifyBot(command_prefix='!', intents=intents)




# Message Functionality
# async def send_message(message: Message, user_message: str) -> None:
#     if not user_message:
#         print('(Message was empty, check intents)')
#         return
#     if is_private := user_message[0] == '?':
#         # User wants to privately message the bot
#         user_message = user_message[1:]
#     try:
#         response: str = get_response(user_message)
#         if is_private:
#             await message.author.send(response)
#         else:
#             await message.channel.send(response)
#     except Exception as e:
#         print(e)


# Bot Startup
# @client.event
# async def on_ready() -> None:
#     print(f'{client.user} is now running!')
#     print("--------------------------------")


# # Message Handler
# async def on_message(message: Message) -> None:
#     if message.author == client.user:
#         # Bot message
#         return
    
#     username: str = str(message.author)
#     user_message: str = message.content
#     channel: str = str(message.channel)

#     print(f'[{channel} {username}: "{user_message}"')
#     await send_message(message, user_message)