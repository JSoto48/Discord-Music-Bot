import discord
from song import Song, SpotifySong, SoundcloudSong


def getPausedEmbed(song: Song, user: discord.User) -> discord.Embed:
    pasuedEmbed: discord.Embed = discord.Embed(
        title='Music Paused',
        colour=discord.Color.dark_gold()
    )
    if type(song) is SpotifySong or type(song) is SoundcloudSong:
        pasuedEmbed.set_thumbnail(url=song.thumbnailUrl)

    pasuedEmbed.set_footer(text=(f'By: {user.display_name}'), icon_url=user.display_avatar)
    return pasuedEmbed


def getLoadingEmbed(title: str = None) -> discord.Embed:
    loadingEmbed: discord.Embed = discord.Embed(
        title=(title if title else 'Loading...'),
        colour=discord.Color.dark_gold()
    )
    return loadingEmbed


def getPlayingEmbed(song: Song) -> discord.Embed:
    footerText: str = None
    playingEmbed: discord.Embed = discord.Embed(
        title='Now Playing',
        description=(f'{song.title}\nby: {song.getArtistList()}'),
        colour=discord.Color.from_rgb(r=25, g=180, b=27)
    )
    if type(song) is SpotifySong or type(song) is SoundcloudSong:
        playingEmbed.set_thumbnail(url=song.thumbnailUrl)

    if song.requestor.bot:
        footerText = 'Recommended song'
    else:
        footerText = f'Queued by: {song.requestor.display_name}'
    playingEmbed.set_footer(text=footerText, icon_url=song.requestor.display_avatar)
    return playingEmbed


def getHelpEmbed() -> discord.Embed:
    helpEmbed: discord.Embed = discord.Embed(
        title="dj Music Bot Overview",
        description=(
            "🎵 **Play Command**  </play:1318586886394220637>\n"
            "Play music in a discord server's voice channel\n\n"
            "**Prerequisites:**\n"
            "- Bot must be a member in your server & text channels\n"
            "- You must be in a voice channel\n\n"
            "**Usage:**\n"
            "1. Type `/play` in chat\n"
            "2. Enter a song name/artist or paste a song link from Spotify/SoundCloud in the `query` box\n"
            "3. Select from search results or press enter with a link\n"
            "4. Give the bot a few seconds to load the song\n\n"
            "**Controls:**\n"
            "- Rewind button: Previous song\n"
            "- Play/Pause button: Toggle playback\n"
            "- Skip button: Next song\n\n"
            "**Disconnecting:**\n"
            "- Bot auto-leaves when voice channel empties\n"
            "- Right-click bot → Disconnect (requires permissions)\n\n\n"
            '**😂 Joke Command**  </joke:1317067512374100029>\n'
            "Get a random joke in the current text channel.\n\n"
            "**Prerequisites:**\n"
            "- Bot must be a member in the text channel\n\n"
            "**Usage:**\n"
            "- Usable in server text channels or DMs\n"
            "- Type `/joke` in chat and press enter\n\n\n"
            '**🛠 Need Help?**\n'
            'Join our [Support Server](https://discord.gg/Qb4dU3Wx76) for assistance!'
        ),
        colour=discord.Color.from_rgb(r=213, g=202, b=234)
    )
    return helpEmbed



