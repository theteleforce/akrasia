import threading
import os
import constants as c

from datetime import datetime as dt
from time import sleep

class Logger(threading.Thread):
    def __init__(self, bot_log, log_type):
        self.__queue = []
        self.bot_log = bot_log
        self.log_type = log_type

        threading.Thread.__init__(self, target=self.__main_loop)
        self.start()

    def add_server_from_message(self, init_message):
        log_path = "{}/{}.{}".format(c.LOGS_DIR, init_message.guild.id, self.log_type)
        if os.path.exists(log_path):
            return False

        with open(log_path, "w+") as _:
            self.bot_log.info("Created log for server {} (id: {}) at {}".format(init_message.guild.name, init_message.guild.id, log_path))

    def log(self, message):
        self.__queue.append(message)

    def __main_loop(self):
        self.bot_log.info("starting main loop for logger (type: {})".format(self.log_type))
        while True:
            if len(self.__queue) > 0:
                message = self.__queue[0]
                if message.guild is not None:
                    with open("{}/{}.{}".format(c.LOGS_DIR, message.guild.id, self.log_type), "a") as f: # assume the OS is going to do the caching and flushing for us
                        f.write("[{}] {} | {} ({}): {}\n".format(dt.now().strftime(c.LOG_DATETIME_FORMAT), message.channel.name, message.author.name, message.author.id, message.content))
                    del self.__queue[0]
                else:
                    with open("{}/{}.{}".format(c.LOGS_DIR, message.author.id, self.log_type), "a") as f: # assume the OS is going to do the caching and flushing for us
                        f.write("{} | {} ({}): {}\n".format(dt.now().strftime(c.LOG_DATETIME_FORMAT), message.author.name, message.author.id, message.content))
                    del self.__queue[0]
            else:
                sleep(c.LOG_SLEEP_TIME[self.log_type])
