from os import environ
from dotenv import load_dotenv
from bot import MusicBot


# Entry Point
def main() -> None:
    load_dotenv()
    TOKEN = environ.get('DISCORD_BOT_KEY')
    myBot: MusicBot = MusicBot()
    myBot.run(token=TOKEN)
    

if __name__ == '__main__':
    main()
