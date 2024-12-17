import yt_dlp as youtube_dl
import os


class Song():
    def __init__(self, title: str = None, artist: str = None):
        self.title = title
        self.artist = artist
        self.songInfo = None

    def downloadTrack(self):
        DOWNLOAD_FOLDER = os.getcwd() + '\\audio_cache\\'
        ytdl_opts = {
        'format': 'bestaudio/best',         # Get the best audio quality
        'extractaudio': True,               # Extract audio only
        'audioformat': 'mp3',               # Convert to MP3 format
        'noplaylist': True,                 # Don't download playlists
        'quiet': True,                      # Show progress
        'postprocessors': [{                # Post-process audio to convert to MP3
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '320',      # Audio quality (bitrate)
        }],
        'default_search': 'ytsearch1',       # Limit search to the first result
        'quiet': True,                       # Suppress console output for faster processing
        'no_warnings': True,                 # Suppress warnings
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, self.title),
        }

        os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)
        searchName = self.artist + ' ' + self.title

        with youtube_dl.YoutubeDL(ytdl_opts) as ytdl:
            trackInfo = ytdl.extract_info(f'ytsearch{searchName}', download=False)
        
        print("in search")
            # try:
            #      ytdl.download(self.artist+self.title)
            # except Exception as e:
            #     print(f"An error occurred: {e}")
