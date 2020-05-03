import os

from akrasia import Akrasia
from constants import DEFAULT_BACKGROUND_LOOPS, DEFAULT_MODULES, DIRECTORIES
from database_utils import update_database
from hooks import default_hooks

def ensure_directories():
    for directory in DIRECTORIES:
        if not os.path.exists(directory):
            os.mkdir(directory)


if __name__ == "__main__":
    ensure_directories()
    update_database()

    custom_hooks = []
    custom_modules = []
    bot = Akrasia(modules=DEFAULT_MODULES + custom_modules, background_loops=DEFAULT_BACKGROUND_LOOPS, hooks=[default_hooks] + custom_hooks)
    bot.run()
