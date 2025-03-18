from os import environ
from dotenv import load_dotenv
from bot import MusicBot


# Entry Point
def main() -> None:
    load_dotenv()
    dj: MusicBot = MusicBot()
    dj.run(token=environ.get('DISCORD_BOT_KEY'))
    

if __name__ == '__main__':
    main()
