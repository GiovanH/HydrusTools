import logging

import colorama
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

def get_logger(name) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)

    colored_streamhandler = logging.StreamHandler()
    colored_streamhandler.setLevel(logging.INFO)
    colored_streamhandler.setFormatter(ColorFormatter('%(name)s %(message)s'))

    logger.addHandler(colored_streamhandler)

    return logger
