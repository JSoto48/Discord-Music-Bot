from discord import Client, Message, Intents
from testingClass import SpotifyAPI


class DiscordClient(Client):
    # Initializes the Discord client and Spotify API 
    def __init__(self):
        intents: Intents = Intents.default()
        intents.message_content = True
        self.discordClient = super().__init__(intents=intents)
        self.spotifyAPI = SpotifyAPI()
    

    async def on_ready(self):
        if self.spotifyAPI.confirm():
            print("Spotify API initialized successfully!")
        else:
            print("ERROR: Spotify API failed to initialize")

        print(f'Discord bot {self.user} is ready for commands!')
    

    # Message Handler
    async def on_message(self, message: Message):
        channel: str = str(message.channel)
        author = str(message.author)
        user_message: str = message.content
        
        if author == self.user or not user_message:
            return
        elif user_message[0] == '!':
            user_message = user_message[1:]

            print(f'COMMAND:{user_message}')

        print(f'intercepted message: {channel} {author}: "{user_message}"')

        