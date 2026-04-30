from typing import Literal

from discord.ext import commands
from objects.context import context
from discord import Intents, AllowedMentions;
from dotenv import load_dotenv;
from datetime import datetime;
import os, json;
emojisFile = open('./configs/emojis.json')
load_dotenv()
class Pipechart(commands.Bot):
    def __init__(self):
        self._prefix = self._get_prefix()
        super().__init__(
            command_prefix=commands.when_mentioned_or(self.prefix),
            intents=Intents.all(),
            owners_id=[476450702672265216, 1066787377747599381],
            strip_after_prefix=True,
            allowed_mentions=AllowedMentions(replied_user=False, everyone=False, users=False),
            help_command=None
        )
        self.readyAt = datetime.timestamp(datetime.now())
        self.emotes = json.load(emojisFile)
    @property
    def prefix(self) -> str:
        return self._prefix
    @property
    def name(self) -> Literal['Pipechart']:
        return "Pipechart"
    @property
    def id (self) -> Literal[1496060183472902154]:
        return 1496060183472902154
    @property
    def avatar(self):
        return "https://cdn.discordapp.com/avatars/1496060183472902154/877640e5273858c526ea71a5348e1ed0.png"
    
    async def get_context(self, message, *, cls=context):
        return await super().get_context(message, cls=cls)

    def _get_prefix(self) -> str:
        prefix = (
            os.getenv("PREFIX")
            or os.getenv("BOT_PREFIX")
            or "\\\\"
        )
        prefix = prefix.strip().strip('"').strip("'")
        return prefix or "\\\\"

    def _get_token(self) -> str:
        token = (
            os.getenv("DISCORD_TOKEN")
            or os.getenv("TOKEN")
            or os.getenv("Token")
            or os.getenv("BOT_TOKEN")
        )
        if not token:
            raise RuntimeError(
                "Missing bot token. Set DISCORD_TOKEN in .env (without quotes)."
            )

        token = token.strip().strip('"').strip("'")
        if token.count(".") != 2:
            raise RuntimeError(
                "Bot token appears malformed. Use your full Discord token in .env."
            )
        return token

    async def init(self):   
        async with self:
            for dir in os.listdir('./cogs'):
                    for file in os.listdir(f'./cogs/{dir}'):
                        if file.endswith('.py'):
                            extension = f'cogs.{dir}.{file[:-3]}'
                            try:
                                await self.load_extension(extension)
                            except commands.errors.NoEntryPointError:
                                # Helper modules can live in cogs directories but are not extensions.
                                continue
            await self.load_extension('jishaku')
            await self.start(self._get_token())