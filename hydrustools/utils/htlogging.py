import functools
import logging
import logging.handlers
import os

import colorama
from colorama import Fore, Style

colorama.init(autoreset=True)

@functools.lru_cache
def fmtRecordName(name: str) -> str:
    return name.replace("hydrustools.", "")

class ColorFormatter(logging.Formatter):
    def format(self, record) -> str:
        record = logging.makeLogRecord(record.__dict__)
        record.name = fmtRecordName(record.name)

        if record.levelno == logging.DEBUG:
            color = Fore.LIGHTBLACK_EX
        elif record.levelno == logging.ERROR:
            color = Fore.RED
        elif record.levelno == logging.WARNING:
            color = Fore.YELLOW
        elif record.levelno == logging.INFO:
            color = Fore.WHITE
        else:
            color = Fore.MAGENTA
        return f"{color}{super().format(record)}{Style.RESET_ALL}"


# Use the LogLevel of the module to filter output
# without preventing child handlers from processing it
class PerModuleConsoleFilter(logging.Filter):
    def __init__(self, log_level=logging.INFO):
        super().__init__()
        self.log_level: int = log_level
        self._levels: dict[str, int] = {}

    def set_level(self, name: str, level: int):
        self._levels[name] = level

    def setLevel(self, log_level):
        self.log_level = log_level

    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name
        while name:
            if name in self._levels:
                return record.levelno >= self._levels[name]
            parent = name.rsplit(".", 1)
            name = parent[0] if len(parent) > 1 else ""
        return record.levelno >= self.log_level


def configure_logging():
    s_handler = logging.StreamHandler()
    s_handler.setLevel(level=logging.DEBUG)
    s_handler.setFormatter(ColorFormatter(
        '%(asctime)s [%(name)s] %(message)s',
        datefmt='%H:%M:%S'
    ))
    s_filter = PerModuleConsoleFilter(log_level=logging.INFO)
    s_handler.addFilter(s_filter)

    f_handler = logging.handlers.RotatingFileHandler(
        "debug.log", encoding='utf-8',
        maxBytes=int(2.5*10**8),
        backupCount=2
    )
    f_handler.setLevel(logging.DEBUG)
    f_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s %(message)s [%(filename)s:%(lineno)d in %(funcName)s]'
    ))

    root_logger = logging.getLogger()
    root_logger.addHandler(s_handler)
    root_logger.addHandler(f_handler)
    root_logger.setLevel(logging.DEBUG)  # Root must pass everything through

    loglevel_envar: str | None = os.environ.get('LOGLEVEL')
    if loglevel_envar:
        loglevel: int | str = logging._nameToLevel.get(loglevel_envar.upper(), loglevel_envar)
        print("Setting loglevel to", loglevel)
        s_filter.setLevel(loglevel)
        # root_logger.setLevel(loglevel)

    logging.getLogger("urllib3.connectionpool").setLevel(logging.WARNING)
