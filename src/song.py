import os
import discord
import yt_dlp

YTDL_OPS = {
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
    'default_search': 'ytsearch1'       # Limit search to the first result
}


# Base Class Object
class Song():
    def __init__(self, id: str, title: str, artists: list, requestor: discord.User, audioPath: str = None):
        self.id: str = id
        self.title: str = title
        self.artists: list[str] = artists
        self.requestor: discord.User = requestor
        self.audioPath: str = audioPath
        self.skipped: bool = False


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


    def getAudioPath(self) -> str:
        return self.audioPath



class SpotifySong(Song):
    def __init__(self, id: str, title: str, artists: list, requestor: discord.User,
                guildFolderPath: str, duration: float, thumbnailUrl: str, explicit: bool):
        super().__init__(id, title, artists, requestor)
        self.guildFolderPath = guildFolderPath
        self.duration: float = duration                         # TODO: Extract duration from yt download, currently in ms from spotify
        self.thumbnailUrl: str = thumbnailUrl
        self.explicit: bool = explicit


    def deleteFile(self):
        if self.audioPath is None:
            return
        elif os.path.exists(self.audioPath):
            os.remove(self.audioPath)
            self.audioPath = None


    def getAudioPath(self) -> str:
        if not os.path.exists(self.guildFolderPath):
            os.makedirs(self.guildFolderPath)
        songBasePath: str = os.path.join(self.guildFolderPath, self.id)
        songPath: str = f"{songBasePath}.mp3"
        if os.path.exists(songPath):
            return songPath
        elif self.audioPath != None and os.path.exists(self.audioPath):
            return self.audioPath

        YTDL_OPS.update({'outtmpl':songBasePath})
        query: str = f'{self.artists[0]} - {self.title}'
        if self.explicit:
            query += ' explicit'
        query += ' audio'
        with yt_dlp.YoutubeDL(YTDL_OPS) as ytdl:
            try:
                ytdl.download([query])
            except Exception as e:
                print(f'YT Download Error: {e}')
        if os.path.exists(songPath):
            self.audioPath = songPath
        return self.audioPath



class SoundcloudSong(Song):
    def __init__(self, id: str, title: str, artists: list, requestor: discord.User, streamURL: str,
                duration: float, thumbnailUrl: str):
        super().__init__(id=id, title=title, artists=artists, requestor=requestor, audioPath=streamURL)
        self.duration: float = duration                         # TODO: convert
        self.thumbnailUrl: str = thumbnailUrl


        