import os
import discord
import yt_dlp


# Base Class Object
class Song():
    def __init__(self, id: str, title: str, artists: list, requestor: discord.User):
        self.title: str = title
        self.artists: list[str] = artists
        self.requestor: discord.User = requestor
        self.id: str = id

    def getArtist(self) -> str:
        if len(self.artists) < 1:
            return None
        return self.artists[0]
    
    def getArtistList(self) -> str:
        if len(self.artists) < 1:
            return None
        artistList: str = ''
        for i, artist in enumerate(self.artists):
            if i == 0:
                artistList = artist
            else:
                artistList += f', {artist}'
        return artistList



class SpotifySong(Song):
    def __init__(self, id: str, title: str, artists: list, requestor: discord.User,
    duration: float, thumbnailUrl: str, explicit: bool):
        super().__init__(id, title, artists, requestor)
        self.duration: float = duration                         # TODO: Extract duration from yt download, currently in ms from spotify
        self.thumbnailUrl: str = thumbnailUrl
        self.explicit: bool = explicit
        self.source: str = 'SP'
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
        songBasePath: str = os.path.join(folderPath, self.id)
        songPath: str = f"{songBasePath}.mp3"
        if os.path.exists(songPath):
            return songPath
        elif self.__filePath != None and os.path.exists(self.__filePath):
            return self.__filePath
        
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
            'outtmpl': songBasePath
        }

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
    
    

class SoundcloudSong(Song):
    def __init__(self, id: str, title: str, artists: list, requestor: discord.User, url: str):
        super().__init__(id, title, artists, requestor)
        self.__url = url



        