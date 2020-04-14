import constants as c
import discord
import logging
import os
import sqlalchemy as db

from asyncio import ensure_future, get_event_loop, sleep
from database_utils import Alias, init_databases, get_or_init_server
from json import load
from logger import Logger
from message_utils import send_lines
from random import choice
from sqlalchemy.orm import sessionmaker


logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
log = logging.getLogger(__name__) # use a logger unique to akrasia

class Akrasia(discord.Client):
    def __init__(self, modules=None, background_loops=None):
        super().__init__()
        self.db_engine, self.db_session_builder = self.init_db_connection()
        self.event_loop = get_event_loop()
        self.version = "0.1.0"
        self.background_loops = background_loops
        self.bot_log = log
        self.command_prefix = c.COMMAND_PREFIX # use default unless assigned in config
        self.database_uri = None
        self.audit_logger = Logger(log, "audit")
        self.status_list = ["with electrons"]
        self.change_status_timer = c.CHANGE_STATUS_TIMER
        self.help_messages = c.DEFAULT_HELP_DICT

        self.command_dict = {
            "addalias": self.add_alias, # tested
            "aliases": self.aliases, # tested
            "deletealias": self.delete_alias, # tested
            "echo": self.echo, # tested
            "help": self.help
        }

        if modules is not None:
            for module in modules:
                for keyword, function_help_pair in module.items():
                    if keyword not in self.command_dict:
                        self.command_dict[keyword] = function_help_pair[0]
                        self.help_messages[keyword] = function_help_pair[1]
                    else:
                        log.warning("Failed to add modular function {} because a function with that keyword already existed!")

    def run(self):
        with open("actual_config_shhh.json") as f:
            config = load(f)
            c.HOME_SERVER_ID = config["home_server"]
            c.AUTHOR_ID = config["author_id"]
            c.DEFAULT_RETURN_MESSAGE = "Something went wrong (please contact <@{}> via DMs)".format(c.AUTHOR_ID)
            self.status_list = config["statuses"]
            self.change_status_timer = config["change_status_timer"]
            self.command_prefix = config["command_prefix"]
            token = config["token"]

            if config["database_uri"]:
                self.database_uri = config["database_uri"]

        if self.background_loops is not None:
            for loop_function in self.background_loops: # insert all of the background loops into the client's event loop
                ensure_future(loop_function(self))

        super().run(token)

    @staticmethod
    def init_db_connection():
        database_uri = "sqlite:///{}/{}/{}".format(os.getcwd(), c.DATABASE_DIR, c.MAIN_DATABASE_NAME)
        engine = db.create_engine(database_uri)
        init_databases(engine)
        if os.path.exists(database_uri[10:]):
            log.info("Connected to existing database at {}".format(database_uri))
        else:
            log.info("Created new database at {}".format(database_uri))

        session_builder = sessionmaker(bind=engine) # create the tool we'll use to make sessions in the future
        return engine, session_builder

    # Hooks for Discord events
    async def on_ready(self):
        log.info("successfully logged in with version: {}".format(self.version))

    async def on_message(self, message):
        if message.author == self.user: # avoid feedback loops
            return

        if len(message.content) > len(self.command_prefix) and message.content[:len(self.command_prefix)] == self.command_prefix: # don't get tripped on images/files that have no message.content
            self.audit_logger.log(message)
            await self.handle_command(message)

        clean_content = message.clean_content.lower() if message.clean_content is not None else None
        if clean_content:
            for hook in c.TEXT_HOOKS:
                if hook in message.clean_content.lower():
                    await self.respond_to_hook(message, hook)
                    return # don't let the bot spam if someone sends a message with 60 triggers

    async def handle_command(self, message):
        command_content = message.content[c.PREFIX_LENGTH:].split(" ") # cut off the prefix
        command_args = self.__get_command_args(command_content) # None if len(command_content) == 1 else command_content[1:]

        session = self.db_session_builder()
        try:
            command_keyword = command_content[0].lower()
            command_function = self.command_dict.get(command_keyword)
            if command_function is None: # if it's not a hardcoded command, check to see if it's an alias
                aliased_command = session.query(Alias).filter(db.and_(Alias.server_id == message.guild.id, Alias.alias == command_keyword)).first()
                if aliased_command is None:
                    raise Exception("unknown command recieved: {}".format(command_keyword)) # early exit and close the session
                else:
                    aliased_function_parts = aliased_command.true_function.split(" ")
                    command_function = self.command_dict.get(aliased_function_parts[0])
                    if len(aliased_function_parts) > 1:
                        command_args = aliased_function_parts[1:] + command_args

            command_reply = await command_function(self, message, command_args, session)
            if command_reply:
                await message.channel.send(command_reply)
        except Exception as e:
            if "unknown command recieved" in str(e):
                log.info("{}".format(e))
            else:
                log.error("{}".format(e))
                await message.channel.send(c.DEFAULT_RETURN_MESSAGE)
            session.rollback()
        finally:
            session.commit()
            session.close()

    @staticmethod
    def __get_command_args(command_content):
        if len(command_content) == 1:
            return []

        command_args = []
        current_arg = []
        in_quotes = False
        for word in command_content[1:]:
            if word[0] == '"':
                word = word[1:]
                in_quotes = True
            if word[-1] == '"':
                word = word[:-1]
                in_quotes = False
            current_arg.append(word)
            if not in_quotes:
                command_args.append(" ".join(current_arg))
                current_arg = []
        if len(current_arg) > 0: # clean up any unclosed quotes
            command_args.append(" ".join(current_arg))

        return command_args

    async def respond_to_hook(self, message, hook):
        if hook == "akrasia,":
            await message.channel.send(choice(c.MAGIC_8_BALL_RESPONSES))

    # Command handling
    async def echo(self, _, message, command_args, __):
        if message.author.id != c.AUTHOR_ID:
            return "You don't have permission to run that command (required permissions: author)!"

        if len(command_args) == 0:
            return "But nobody came."

        try:
            if len(command_args) > 1:
                echo_message = " ".join(command_args[1:])
                if len(command_args[0]) > 2 and command_args[0][:2] == "<#":
                    command_args[0] = command_args[0][2:-1] # turn a channel identifier like <#channelid> into channelid

                await self.get_channel(int(command_args[0])).send(echo_message)
                log.info("Echoed the following message to channel {}: {}".format(command_args[0], echo_message))
                return
        except discord.errors.HTTPException as e: # if that failed, we just echo the full command_args back to the channel
            log.warning("Couldn't echo message to channel {}; error was: {}".format(command_args[0], e))
        except ValueError: # if we couldn't parse command_args[0] as int, that's fine
            pass

        echo_message = " ".join(command_args)
        await message.channel.send(echo_message)
        log.info("Echoed the following message to channel {}: {}".format(message.channel.id, echo_message))

    async def add_alias(self, _, message, command_args, session):
        if not message.author.permissions_in(message.channel).administrator:
            return "You don't have permissions to run that command! (required permissions: administrator)"

        if len(command_args) != 2:
            log.info("Failed to add alias in {} (id: {}); improper syntax".format(message.guild.name, message.guild.id))
            return "Improper syntax (your message should look like this: !addalias {alias} {normal function}"
        true_function = command_args[0].lower()
        alias = command_args[1].lower()
        true_function_keyword = true_function.split(" ")[0]

        true_function_exists = self.command_dict.get(true_function_keyword)
        if true_function_exists is None:
            try: # check if we're aliasing to another alias; if so, map it to the true function of that alias
                existing_alias = session.query(Alias).filter(db.and_(Alias.server_id == message.guild.id and Alias.alias == true_function)).first()
                if existing_alias is None:
                    log.info("Failed to add alias '{} = {}' in {} (id: {}); no such true function existed".format(alias, true_function, message.guild.name, message.guild.id))
                    return "The function you're trying to alias to doesn't exist!"
                else:
                    true_function = existing_alias.true_function
                    log.info("Redirecting alias '{} = {}' in {} (id: {}) to old alias' true function '{}'".format(alias, existing_alias.alias, message.guild.name, message.guild.id, existing_alias.true_function))
            except Exception as e:
                raise Exception("Couldn't look up existing aliases for {}: {}".format(true_function, e))

        try:
            existing_alias = session.query(Alias).filter(db.and_(Alias.server_id == message.guild.id, Alias.alias == alias)).first()
            if existing_alias is not None:
                log.info("Failed to add alias '{} = {}' in {} (id: {}); given alias already existed for {}".format(alias, true_function, message.guild.name, message.guild.id, existing_alias.true_function))
                return "Alias already exists! (you can delete it using !deletealias)"
        except Exception as e:
            raise Exception("Couldn't check if alias {} already existed: {}".format(alias, e))

        alias_server = await get_or_init_server(self, message, session)
        if len(alias_server.aliases) > c.MAX_ALIASES_PER_SERVER:
            log.error("Couldn't add alias to server {} (id: {}) because it had exceeded max aliases".format(message.guild.name, message.guild.id))
            return "Too many aliases on this server ({}). You should delete some with !deletealias".format(c.MAX_ALIASES_PER_SERVER)
        try:
            session.add(Alias(alias=alias, true_function=true_function, server=alias_server))
        except Exception as e:
            raise Exception("Error adding alias '{} = {}' to server {} (id: {}); error was {}".format(alias, true_function, message.guild.name, message.guild.id, e))

        return "Added alias {}!".format(alias)

    async def delete_alias(self, _, message, command_args, session):
        if not message.author.permissions_in(message.channel).administrator:
            return "You don't have permissions to run that command! (required permissions: administrator)"

        if len(command_args) != 1:
            log.info("Failed to delete alias in {} (id: {}); improper syntax".format(message.guild.name, message.guild.id))
            return "Improper syntax (your message should look like this: !deletealias {alias}"
        alias = command_args[0].lower()

        try:
            existing_alias = session.query(Alias).filter(db.and_(Alias.server_id == message.guild.id, Alias.alias == alias)).first()
            if existing_alias is None:
                log.info("Failed to remove alias '{}' in {} (id: {}); no such alias exists in database".format(alias, message.guild.name, message.guild.id))
                return "No such alias exists! (you can delete it using !deletealias)"
        except Exception as e:
            raise Exception("Couldn't check if alias {} already existed: {}".format(alias, e))

        try:
            session.delete(existing_alias)
        except Exception as e:
            raise Exception("Error deleting alias '{} = {}' from server {} (id: {}); error was {}".format(alias, existing_alias.true_function, message.guild.name, message.guild.id, e))

        return "Deleted alias {}!".format(alias)

    async def aliases(self, _, message, __, session):
        if not message.author.permissions_in(message.channel).administrator:
            return "You don't have permissions to run that command! (required permissions: administrator)"

        if message.guild is None:
            return "Cannot list aliases outside of a server!"
        server_aliases = session.query(Alias).filter(Alias.server_id == message.guild.id).all()
        if len(server_aliases) == 0 or server_aliases is None:
            return "No aliases found!"

        await message.channel.send("{} aliases:\n".format(len(server_aliases)))
        send_string = ""
        for alias in server_aliases:
            alias_string = "{} => {} ".format(alias.alias, alias.true_function)

            if len(send_string) + len(alias_string) > c.MAX_CHARS_PER_MESSAGE:
                await message.channel.send(send_string)
                send_string = alias_string
            else:
                send_string += alias_string + "\n"
        await message.channel.send(send_string)
        await sleep(c.SEND_CYCLE_WAIT_TIME)

    async def help(self, _, message, command_args, session):
        if len(command_args) == 0:
            commands = [keyword for keyword in self.command_dict]
            commands.sort() # alphabetize list so it's easier to find specific commands
            message_lines = ["Must run !help with a specific command! Here's a list of commands installed on this server:"] + commands
            await send_lines(message.author, message_lines)
            return

        keyword = command_args[0]
        keyword_is_function = self.command_dict.get(keyword)
        if keyword_is_function is None:
            aliased_command = session.query(Alias).filter(db.and_(Alias.server_id == message.guild.id, Alias.alias == keyword)).first()
            if aliased_command is None:
                return "This server doesn't have that command!"
            else:
                keyword = aliased_command.true_function.split(" ")[0]

        await message.author.send(self.help_messages[keyword])
