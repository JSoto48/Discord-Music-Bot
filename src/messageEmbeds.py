import discord
from song import Song


def getPausedEmbed(song: Song, user: discord.User) -> discord.Embed:
    pasuedEmbed: discord.Embed = discord.Embed(
        title='Music Paused',
        colour=discord.Color.dark_gold()
    )
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
    embed = discord.Embed(
        title='Now Playing',
        description=(f'{song.title} \nby {song.getArtistList()}\n'),
        colour=discord.Color.from_rgb(r=25, g=180, b=27)
    )
    embed.set_thumbnail(url=song.thumbnailUrl)
    if song.requestor.bot:
        footerText = 'Recommended song'
    else:
        footerText = f'Queued by: {song.requestor.display_name}'
    embed.set_footer(text=footerText, icon_url=song.requestor.display_avatar)
    return embed

