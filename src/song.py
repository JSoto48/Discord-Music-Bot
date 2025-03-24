import os
import discord
import yt_dlp


ytdl_opts = {
    'format': 'bestaudio/best',         # Get the best audio quality
    'extractaudio': True,               # Extract audio only
    'audioformat': 'mp3',               # Convert to MP3 format
    'noplaylist': True,                 # Don't download playlists
    'quiet': True,                      # Suppress console output for faster processing
    'no_warnings': True,                # Suppress warnings
    'postprocessors': [{                # Post-process audio to convert to MP3
        'key': 'FFmpegExtractAudio',
        'preferredcodec': 'mp3',
        'preferredquality': '128',      # Audio quality (bitrate) - matches discord.player bitrate
    }],
    'default_search': 'ytsearch1',      # Limit search to the first result
}


class Song():
    def __init__(self, id: str, title: str, artists: list, requestor: discord.User,
    duration: float = None, thumbnailUrl: str = None):
        self.title: str = title
        self.artists: list[str] = artists                       # Primary artist always at index 0
        self.requestor: discord.User = requestor
        self.duration: float = duration                         # TODO: Extract duration from yt download, currently in ms from spotify
        self.thumbnailUrl: str = thumbnailUrl
        self.explicit: bool = False                             # TODO: Add in song declaration
        self.source: str = None                                 
        self.__id: str = id
        self.__filePath: str = None
    
    
    def deleteFile(self):
        if self.__filePath is None:
            return
        elif os.path.exists(self.__filePath):
            os.remove(self.__filePath)
            self.__filePath = None


    def getFilePath(self, folderPath: str) -> str:
        if not os.path.exists(folderPath):
            os.makedirs(folderPath)
        songBasePath: str = os.path.join(folderPath, self.__id)
        songPath: str = f"{songBasePath}.mp3"
        if os.path.exists(songPath):
            return songPath
        elif self.__filePath != None and os.path.exists(self.__filePath):
            return self.__filePath
        ytdl_opts.update({'outtmpl': songBasePath})

        query: str = f'{self.artists[0]} - {self.title}'
        if self.explicit:
            query += ' explicit'
        query += ' audio'
        with yt_dlp.YoutubeDL(ytdl_opts) as ytdl:
            try:
                ytdl.download([query])
            except Exception as e:
                print(f'YT Download Error: {e}')
        if os.path.exists(songPath):
            self.__filePath = songPath
        return self.__filePath
    

