import logging
import colorama
class Formater(logging.Formatter):
    yellow = "\x1b[33;20m"
    red = "\x1b[31;20m"
    reset = "\x1b[0m"
    blue = "\u001b[36m"
    format = "%(asctime)s - %(levelname)s - %(module)s: %(message)s (%(filename)s:%(lineno)d)"

    FORMATS = {
        logging.WARNING: yellow + format + reset,
        logging.ERROR: red + format + reset,
        logging.CRITICAL: red + format + reset,
        logging.INFO: blue + format + reset,
        logging.DEBUG: format
    }

    def format(self, record):
        log_fmt = self.FORMATS.get(record.levelno)
        formatter = logging.Formatter(log_fmt)
        return formatter.format(record)

def setup_logging():
    colorama.init()
    log = logging.getLogger()
    
    log.setLevel(logging.DEBUG)

    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(Formater())

    log.addHandler(console)