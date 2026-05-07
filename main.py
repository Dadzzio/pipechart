from objects.bot import Pipechart
from utils.logging import setup_logging
import logging
import asyncio;
setup_logging()

log = logging.getLogger(__name__)
log.info("Starting PIPECHART-BOT...")

asyncio.run(Pipechart().init())