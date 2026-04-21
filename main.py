from objects.bot import Pipechart
from utils.logging import setup_logging
import asyncio;
setup_logging()

print("""                   
        Starting PIPECHART-BOT...    
""")

asyncio.run(Pipechart().init())