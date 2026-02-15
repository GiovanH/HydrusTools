import logging
import logging.handlers
import colorama
import os
from colorama import Fore, Style

colorama.init(autoreset=True)

class ColorFormatter(logging.Formatter):
    def format(self, record) -> str:
        if record.levelno == logging.DEBUG:
            color = Fore.LIGHTWHITE_EX
        if record.levelno == logging.ERROR:
            color = Fore.RED
        elif record.levelno == logging.WARNING:
            color = Fore.YELLOW
        else:
            color = Fore.WHITE
        return f"{color}{super().format(record)}{Style.RESET_ALL}"

def configure_logging():
    s_handler = logging.StreamHandler()
    s_handler.setLevel(level=logging.INFO)
    s_handler.setFormatter(ColorFormatter(
        '%(asctime)s [%(name)s] %(message)s',
        datefmt='%H:%M:%S'
    ))

    loglevel = os.environ.get('LOGLEVEL')
    if loglevel:
        s_handler.setLevel(loglevel)

    f_handler = logging.handlers.RotatingFileHandler("debug.log")
    f_handler.setLevel(logging.DEBUG)
    f_handler.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s %(message)s [%(filename)s:%(lineno)d in %(funcName)s]'))

    root_logger = logging.getLogger()
    root_logger.addHandler(s_handler)
    root_logger.addHandler(hdlr=f_handler)
    root_logger.setLevel(logging.INFO)

