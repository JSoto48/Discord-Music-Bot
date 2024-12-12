from os import environ
from dotenv import load_dotenv
from discordBot import DiscordClient



# Entry Point
def main() -> None:
    myClient = DiscordClient()
    load_dotenv()
    myClient.run(token=environ.get('DISCORD_BOT_KEY'))
    

if __name__ == '__main__':
    main()


