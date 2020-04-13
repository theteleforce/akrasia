import os

from akrasia import Akrasia
from constants import DEFAULT_BACKGROUND_LOOPS, DEFAULT_MODULES, DIRECTORIES

def ensure_directory():
    for directory in DIRECTORIES:
        if not os.path.exists(directory):
            os.mkdir(directory)


if __name__ == "__main__":
    bot = Akrasia(modules=DEFAULT_MODULES, background_loops=DEFAULT_BACKGROUND_LOOPS)
    bot.run()
