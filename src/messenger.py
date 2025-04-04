"""AI chat, provides history"""
import discord
from discord.ext import commands
from g4f import Client, Provider

ERROR_MSG: str = 'Please try again later. (=ʘᆽʘ=)'
MAX_MSG_LENGTH: int = 2000

class AiMessager(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot: commands.Bot = bot
        self.__aiModel = Client(provider=Provider.TeachAnything)
        self.__chats: dict[int:list[dict]] = dict()
    

    @commands.Cog.listener()
    async def on_ready(self):
        print(f'{__name__} loaded to {self.bot.user}')


    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        user_message: str = message.content
        responseList: list[str] = None
        if message.author.id == self.bot.user.id or user_message == '':
            # Messages sent from this bot or messages with no text(ex. images, embeds)
            return
        elif str(self.bot.user.id) in user_message:
            # Bot was tagged with @bot_username
            tag: str = f'<@{self.bot.user.id}>'
            responseList = self.__getResponse(prompt=user_message.replace(tag, ''), guild_id=message.guild.id)
        elif isinstance(message.channel, discord.channel.DMChannel):
            responseList = self.__getResponse(prompt=user_message, guild_id=message.channel.id)
        await self.sendStringList(stringList=responseList, message=message, dm=isinstance(message.channel, discord.channel.DMChannel))
    

    async def sendStringList(self, stringList: list[str], message: discord.Message, dm: bool = False) -> None:
        listLen: int = len(stringList)
        if listLen < 1:
            return
        elif listLen > 1:
            for i, textBlock in enumerate(stringList):
                if i == 0 and dm == False:
                    await message.reply(textBlock)
                else:
                    await message.channel.send(textBlock)
        else:
            if dm == True:
                await message.channel.send(stringList[0])
            else:
                await message.reply(stringList[0])


    def __getResponse(self, prompt: str, guild_id: int) -> list[str]:
        self.__pushHistory(role='user', content=prompt, guild_id=guild_id)
        try:
            response = self.__aiModel.chat.completions.create(
                messages=self.__chats.get(guild_id),
                model='gemini-1.5-flash',
                web_search = False
            )
        except:
            return [ERROR_MSG]
        msg: str = response.choices[0].message.content
        if msg is None or len(msg) == 0:
            return [ERROR_MSG]
        elif len(msg) < MAX_MSG_LENGTH:
            self.__pushHistory(role='assistant', content=msg, guild_id=guild_id)
            return [msg]
        else:
            self.__pushHistory(role='assistant', content=msg, guild_id=guild_id)
            msgList: list[str] = list()
            textBlock: str = ''
            for i, char in enumerate(msg):
                textBlock += char
                if i == (len(msg)-1) or ((i+1) % MAX_MSG_LENGTH) == 0:
                    msgList.append(textBlock)
                    textBlock = ''
            return msgList


    def __pushHistory(self, role: str, content: str, guild_id: int) -> None:
        # History is a list of each message sent
        # Messages are a dictionary containing two keys, role and content
        message: dict = {
            'role': role,
            'content': content
        }
        history: list[dict] = self.__chats.get(guild_id)
        if history is None:
            history = list()
        elif len(history) > 10:
            history.pop(0)
        history.append(message)
        self.__chats.update({guild_id:history})
    



async def setup(bot: commands.Bot):
    await bot.add_cog(AiMessager(bot))



