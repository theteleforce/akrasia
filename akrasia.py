import constants as c
import discord
import logging
import os
import sqlalchemy as db

from asyncio import ensure_future, get_event_loop
from database_utils import Alias, AuditLogEntry, init_databases, get_or_init_server, get_or_init_user
from json import load
from logger import Logger
from message_utils import MessageWrapper, send_lines
from re import match
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql.expression import func
from sys import stdout


class Akrasia(discord.Client):
    def __init__(self, modules=None, background_loops=None, hooks=None):
        logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s", stream=stdout)
        self.bot_log = logging.getLogger(__name__)  # use a logger unique to akrasia

        super().__init__()
        self.db_engine, self.db_session_builder = self.init_db_connection()
        self.event_loop = get_event_loop()
        self.version = "0.2.0"
        self.background_loops = background_loops
        self.command_prefix = c.COMMAND_PREFIX # use default unless assigned in config
        self.database_uri = None
        self.user_command_cooldown = c.DEFAULT_COMMAND_COOLDOWN
        self.user_hook_cooldown = c.DEFAULT_HOOK_COOLDOWN
        self.audit_logger = Logger()
        self.status_list = ["with electrons"]
        self.change_status_timer = c.CHANGE_STATUS_TIMER
        self.help_messages = c.DEFAULT_HELP_DICT

        self.command_dict = {
            "addalias": self.add_alias, # tested
            "aliases": self.aliases, # tested
            "auditlog": self.audit_log,
            "deletealias": self.delete_alias, # tested
            "echo": self.echo, # tested
            "help": self.help,
            "setserver": self.set_server # tested
        }
        self.hooks_dict = {}

        if modules is not None:
            for module in modules:
                for keyword, function_help_pair in module.items():
                    if keyword not in self.command_dict:
                        self.command_dict[keyword] = function_help_pair[0]
                        self.help_messages[keyword] = function_help_pair[1]
                    else:
                        self.bot_log.warning("Failed to add modular function {} because a function with that keyword already existed!")

        if hooks is not None:
            for hook in hooks:
                for hook_regex, hook_function in hook.items():
                    if hook_regex not in self.hooks_dict:
                        self.hooks_dict[hook_regex] = hook_function
                    else:
                        self.bot_log.warning("Failed to add hook {} because a hook with that regex already existed!")

    def run(self):
        with open("config.json") as f:
            config = load(f)
            c.HOME_SERVER_ID = config["home_server"]
            c.AUTHOR_ID = config["author_id"]
            c.DEFAULT_RETURN_MESSAGE = "Something went wrong (please contact <@{}> via DMs)".format(c.AUTHOR_ID)
            self.status_list = config["statuses"]
            self.change_status_timer = config["change_status_timer"]
            self.command_prefix = config["command_prefix"]
            self.user_command_cooldown = config["per_user_command_cooldown"]
            self.user_hook_cooldown = config["per_user_hook_cooldown"]
            token = config["token"]

            if config["database_uri"]:
                self.database_uri = config["database_uri"]

        if self.background_loops is not None:
            for loop_function in self.background_loops: # insert all of the background loops into the client's event loop
                ensure_future(loop_function(self))

        super().run(token)

    def init_db_connection(self):
        database_uri = "sqlite:///{}/{}/{}".format(os.getcwd(), c.DATABASE_DIR, c.MAIN_DATABASE_NAME)
        engine = db.create_engine(database_uri)
        init_databases(engine)
        if os.path.exists(database_uri[10:]):
            self.bot_log.info("Connected to existing database at {}".format(database_uri))
        else:
            self.bot_log.info("Created new database at {}".format(database_uri))

        session_builder = sessionmaker(bind=engine) # create the tool we'll use to make sessions in the future
        return engine, session_builder

    # Hooks for Discord events
    async def on_ready(self):
        self.bot_log.info("successfully logged in with version: {}".format(self.version))

    async def on_message(self, message):
        if message.author == self.user: # avoid feedback loops
            return

        if len(message.content) > len(self.command_prefix) and message.content[:len(self.command_prefix)] == self.command_prefix: # don't get tripped on images/files that have no message.content
            await self.handle_command(message)
            return # don't respond both to commands and hooks

        clean_content = message.clean_content.lower() if message.clean_content is not None else None
        if clean_content:
            for hook in self.hooks_dict:
                if match(hook, clean_content):
                    await self.handle_hook(message, hook)
                    return # don't let the bot spam if someone sends a message with 60 triggers

    async def handle_command(self, message):
        command_content = message.content[c.PREFIX_LENGTH:].split(" ") # cut off the prefix
        command_args = self.__get_command_args(command_content) # None if len(command_content) == 1 else command_content[1:]
        command_keyword = None

        session = self.db_session_builder()
        try:
            command_keyword = command_content[0].lower()
            command_function = self.command_dict.get(command_keyword)

            relevant_user = get_or_init_user(self, message, session)
            if relevant_user.last_command_time is not None and (message.created_at - relevant_user.last_command_time).total_seconds() < self.user_command_cooldown:
                self.bot_log.warning("User {} (id: {}) ran another command before their command cooldown was up".format(message.author.name, message.author.id))
                return None
            else:
                relevant_user.last_command_time = message.created_at
                session.commit() # commit here so people can't spam invalid commands and abuse the except: rollback

            if command_function is None: # if it's not a hardcoded command, check to see if it's an alias
                aliased_command = session.query(Alias).filter(db.and_(Alias.server_id == message.guild.id, Alias.alias == command_keyword)).first()
                if aliased_command is None:
                    raise Exception("unknown command recieved: {}".format(command_keyword)) # early exit and close the session
                else:
                    aliased_function_parts = aliased_command.true_function.split(" ")
                    command_function = self.command_dict.get(aliased_function_parts[0])
                    if len(aliased_function_parts) > 1:
                        command_args = aliased_function_parts[1:] + command_args

            if message.guild is None: # if in a DM, set the server to the user's home server, if they have one
                if relevant_user.main_server is not None: # set the guild of the message to the user's main guild
                    home_guild = self.get_guild(relevant_user.main_server_id)
                    message = MessageWrapper(message, home_guild, home_guild.get_member(message.author.id)) # WARNING: if something you're doing is horribly and subtly broken, this is probably why

            self.audit_logger.log(self, message, session) # must audit log *after* setting the server to the home server

            command_reply = await command_function(self, message, command_args, session)
            if command_reply:
                await message.channel.send(command_reply)
        except Exception as e:
            if "unknown command recieved" in str(e):
                self.bot_log.info("{}".format(e))
            else:
                self.bot_log.error("Something went wrong during function {}: {}".format(command_keyword, e))
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
        for word in [w for w in command_content[1:] if len(w) > 0]:
            if word[0] == '"' and len(word) > 2:
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

    async def handle_hook(self, message, hook):
        session = self.db_session_builder()
        try:
            relevant_user = get_or_init_user(self, message, session)
            if relevant_user.last_hook_time is not None and (message.created_at - relevant_user.last_hook_time).total_seconds() < self.user_hook_cooldown:
                self.bot_log.warning("User {} (id: {}) triggered another hook before their hook cooldown was up".format(message.author.name, message.author.id))
                return None
            else:
                relevant_user.last_command_time = message.created_at
                session.commit()  # commit here so people can't spam invalid commands and abuse the except: rollback

            hook_function = self.hooks_dict[hook]

            if message.guild is None:  # if in a DM, set the server to the user's home server, if they have one
                if relevant_user.main_server is not None:  # set the guild of the message to the user's main guild
                    home_guild = self.get_guild(relevant_user.main_server_id)
                    message = MessageWrapper(message, home_guild, home_guild.get_member(message.author.id))  # WARNING: if something you're doing is horribly and subtly broken, this is probably why

            self.audit_logger.log(self, message, session)  # must audit log *after* setting the server to the home server

            hook_reply = await hook_function(self, message, session)
            if hook_reply:
                await message.channel.send(hook_reply)

            if message.guild is not None:
                self.bot_log.info("Responded to hook {} in server {} (id: {})".format(hook, message.guild.name, message.guild.id))
            else:
                self.bot_log.info("Responded to hook {} in DMs with user {} (id: {})".format(hook, message.author.name, message.author.id))
        except Exception as e:
            self.bot_log.error("Something went wrong during hook function for {}: {}".format(hook, e))
            await message.channel.send(c.DEFAULT_RETURN_MESSAGE)
            session.rollback()
        finally:
            session.commit()
            session.close()

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
                self.bot_log.info("Echoed the following message to channel {}: {}".format(command_args[0], echo_message))
                return
        except discord.errors.HTTPException as e: # if that failed, we just echo the full command_args back to the channel
            self.bot_log.warning("Couldn't echo message to channel {}; error was: {}".format(command_args[0], e))
        except ValueError: # if we couldn't parse command_args[0] as int, that's fine
            pass

        echo_message = " ".join(command_args)
        await message.channel.send(echo_message)
        self.bot_log.info("Echoed the following message to channel {}: {}".format(message.channel.id, echo_message))

    async def add_alias(self, _, message, command_args, session):
        if message.guild is None:
            return c.GUILD_REQUIRED_MESSAGE.format(self.command_prefix, "addalias", self.command_prefix)

        if not message.author.guild_permissions.administrator:
            return "You don't have permissions to run that command! (required permissions: administrator)"

        if len(command_args) != 2:
            self.bot_log.info("Failed to add alias in {} (id: {}); improper syntax".format(message.guild.name, message.guild.id))
            return "Improper syntax (your message should look like this: {}addalias [normal function] [alias]".format(self.command_prefix)
        alias = command_args[1].lower()
        alias = alias[len(c.COMMAND_PREFIX):] if len(alias) > len(c.COMMAND_PREFIX) and alias[:len(c.COMMAND_PREFIX)] == c.COMMAND_PREFIX else alias
        true_function_keyword = command_args[0].split(" ")[0].lower()
        true_function_keyword = true_function_keyword[len(c.COMMAND_PREFIX):] if len(true_function_keyword) > len(c.COMMAND_PREFIX) and true_function_keyword[:len(c.COMMAND_PREFIX)] == c.COMMAND_PREFIX else true_function_keyword
        true_function = true_function_keyword + " " + " ".join(command_args[0].split(" ")[1:]) if len(command_args[0].split(" ")) > 1 else true_function_keyword

        true_function_exists = self.command_dict.get(true_function_keyword)
        if true_function_exists is None:
            try: # check if we're aliasing to another alias; if so, map it to the true function of that alias
                existing_alias = session.query(Alias).filter(db.and_(Alias.server_id == message.guild.id, Alias.alias == true_function)).first()
                if existing_alias is None:
                    self.bot_log.info("Failed to add alias '{} = {}' in {} (id: {}); no such true function existed".format(alias, true_function, message.guild.name, message.guild.id))
                    return "The function you're trying to alias to doesn't exist!"
                else:
                    true_function = existing_alias.true_function
                    self.bot_log.info("Redirecting alias '{} = {}' in {} (id: {}) to old alias' true function '{}'".format(alias, existing_alias.alias, message.guild.name, message.guild.id, existing_alias.true_function))
            except Exception as e:
                raise Exception("Couldn't look up existing aliases for {}: {}".format(true_function, e))

        try:
            existing_alias = session.query(Alias).filter(db.and_(Alias.server_id == message.guild.id, Alias.alias == alias)).first()
            if existing_alias is not None:
                self.bot_log.info("Failed to add alias '{} = {}' in {} (id: {}); given alias already existed for {}".format(alias, true_function, message.guild.name, message.guild.id, existing_alias.true_function))
                return "Alias already exists! (you can delete it using {}deletealias)".format(self.command_prefix)
        except Exception as e:
            raise Exception("Couldn't check if alias {} already existed: {}".format(alias, e))

        alias_server = await get_or_init_server(self, message.guild, session)
        if len(alias_server.aliases) > c.MAX_ALIASES_PER_SERVER:
            self.bot_log.error("Couldn't add alias to server {} (id: {}) because it had exceeded max aliases".format(message.guild.name, message.guild.id))
            return "Too many aliases on this server ({}). You should delete some with {}deletealias".format(c.MAX_ALIASES_PER_SERVER, self.command_prefix)
        try:
            session.add(Alias(alias=alias, true_function=true_function, server=alias_server))
        except Exception as e:
            raise Exception("Error adding alias '{} = {}' to server {} (id: {}); error was {}".format(alias, true_function, message.guild.name, message.guild.id, e))

        return "Added alias {} => {}!".format(alias, true_function)

    async def delete_alias(self, _, message, command_args, session):
        if message.guild is None:
            return c.GUILD_REQUIRED_MESSAGE.format(self.command_prefix, "deletealias", self.command_prefix)

        if not message.author.guild_permissions.administrator:
            return "You don't have permissions to run that command! (required permissions: administrator)"

        if len(command_args) != 1:
            self.bot_log.info("Failed to delete alias in server {} (id: {}); improper syntax".format(message.guild.name, message.guild.id))
            return "Improper syntax (your message should look like this: {}deletealias [alias])".format(self.command_prefix)
        alias = command_args[0].lower()
        alias = alias[len(c.COMMAND_PREFIX):] if len(alias) > len(c.COMMAND_PREFIX) and alias[:len(c.COMMAND_PREFIX)] == c.COMMAND_PREFIX else alias

        try:
            existing_alias = session.query(Alias).filter(db.and_(Alias.server_id == message.guild.id, Alias.alias == alias)).first()
            if existing_alias is None:
                self.bot_log.info("Failed to remove alias '{}' in server {} (id: {}); no such alias exists in database".format(alias, message.guild.name, message.guild.id))
                return "No such alias exists!"
        except Exception as e:
            raise Exception("Couldn't check if alias {} already existed: {}".format(alias, e))

        try:
            session.delete(existing_alias)
        except Exception as e:
            raise Exception("Error deleting alias '{} => {}' from server {} (id: {}); error was {}".format(alias, existing_alias.true_function, message.guild.name, message.guild.id, e))

        return "Deleted alias {}!".format(alias)

    async def aliases(self, _, message, __, session):
        if message.guild is None:
            return c.GUILD_REQUIRED_MESSAGE.format(self.command_prefix, "aliases", self.command_prefix)

        if not message.author.guild_permissions.administrator:
            return "You don't have permissions to run that command! (required permissions: administrator)"

        server_aliases = session.query(Alias).filter(Alias.server_id == message.guild.id).all()
        if len(server_aliases) == 0 or server_aliases is None:
            return "No aliases found!"

        await message.channel.send("{} aliases:\n".format(len(server_aliases)))
        await send_lines(message.channel, ["{} => {} ".format(alias.alias, alias.true_function) for alias in server_aliases])

    async def set_server(self, _, message, command_args, session):
        if len(command_args) == 0: # no args means that this user wants their home server reset
            user = get_or_init_user(self, message, session)
            user.main_server = None
            self.bot_log.info("Reset main server of {} (id: {})".format(message.author.name, message.author.id))
            return "Cleared your home server!"

        server_name_or_id = " ".join(command_args)

        if len(command_args) == 1: # if there was one arg, it might be a server ID
            try:
                supposed_id = int(server_name_or_id)
                server_matching_id = self.get_guild(supposed_id)
                if server_matching_id is not None:
                    main_server = await get_or_init_server(self, server_matching_id, session)
                    user = get_or_init_user(self, message, session)
                    user.main_server = main_server
                    self.bot_log.info("Set main server of {} (id: {}) to {} (id: {})".format(message.author.name, message.author.id, main_server.name, main_server.id))
                    return "Set home server to {}!".format(server_matching_id.name)
            except ValueError:
                pass # if we can't convert to int, that's fine; it's probably a name

        servers_matching_search = [guild for guild in self.guilds if server_name_or_id.lower() in guild.name.lower() and guild.get_member(message.author.id) is not None] # get guilds that a) match the search and b) contain the user
        if len(servers_matching_search) > 1:
            return_string_lines = ["Search returned {} servers:".format(len(servers_matching_search))]
            for server in servers_matching_search:
                return_string_lines.append("    [ID: {}] {} ({} users)".format(server.id, server.name, len(server.members)))
            self.bot_log.info("Couldn't set main server of {} (id: {}) based on query {}: too many results found ({}).".format(message.author.name, message.author.id, server_name_or_id, len(servers_matching_search)))
            return_string_lines.append("Try being more specific, or using one of the IDs given above.")

            if message.guild is None:
                await send_lines(message.author, return_string_lines)
            else:
                await send_lines(message.channel, return_string_lines)
            return None
        elif len(servers_matching_search) == 0:
            self.bot_log.info("Couldn't set main server of {} (id: {}) based on query {}: no results found.".format(message.author.name, message.author.id, server_name_or_id))
            return "No servers found matching that search term!"

        server_matching_id = self.get_guild(servers_matching_search[0].id)
        main_server = await get_or_init_server(self, server_matching_id, session)
        user = get_or_init_user(self, message, session)
        user.main_server = main_server
        self.bot_log.info("Set main server of {} (id: {}) to {} (id: {})".format(message.author.name, message.author.id, main_server.name, main_server.id))
        return "Set home server to {}!".format(server_matching_id.name)

    async def audit_log(self, _, message, command_args, session):
        if message.guild is None:
            return c.GUILD_REQUIRED_MESSAGE.format(self.command_prefix, "auditlog", self.command_prefix)

        if not message.author.guild_permissions.administrator:
            return "You don't have permissions to run that command! (required permissions: administrator)"

        if len(command_args) == 0:
            num_entries = c.DEFAULT_AUDIT_LOG_ENTRIES
            search_term = None
        elif len(command_args) == 1:
            try:
                num_entries = int(command_args[0])
                if num_entries > 10**10: # detects when the first command is a user ID, because nobody would ever request this many messages
                    raise ValueError()
                search_term = None
            except ValueError:
                num_entries = c.DEFAULT_AUDIT_LOG_ENTRIES
                search_term = command_args[0].lower()
        else:
            try:
                num_entries = int(command_args[-1])
                search_term = " ".join(command_args[:-1]).lower()
            except ValueError:
                num_entries = c.DEFAULT_AUDIT_LOG_ENTRIES
                search_term = " ".join(command_args).lower()

        return_lines = []
        if num_entries > c.MAX_AUDIT_LOG_ENTRIES and message.author.id != c.AUTHOR_ID: # allow the bot owner to query arbitrarily many audit log lines
            return_lines.append("You requested too many lines, so here's the maximum ({})".format(return_lines))
            return_lines.append("")
            num_entries = c.MAX_AUDIT_LOG_ENTRIES

        self.bot_log.info("trying to send audit log to user {} (id: {}) based on (num_entries: {}, search_term: {})".format(message.author.name, message.author.id, num_entries, search_term))
        if search_term is not None:
            log_entries = session.query(AuditLogEntry).filter(db.and_(AuditLogEntry.guild_id == message.guild.id, func.lower(AuditLogEntry.message_content).contains(search_term.lower()))).order_by(AuditLogEntry.timestamp.desc()).limit(num_entries).all()
        else:
            log_entries = session.query(AuditLogEntry).filter(AuditLogEntry.guild_id == message.guild.id).order_by(AuditLogEntry.timestamp.desc()).limit(num_entries).all()

        if len(log_entries) == 0:
            self.bot_log.info("no audit log entries found for user {} (id: {}) based on (num_entries: {}, search_term: {})".format(message.author.name, message.author.id, num_entries, search_term))
            return "No commands found matching the search terms (num_entries: {}, search_term: {})".format(num_entries, search_term)

        for entry in reversed(log_entries): # show the five most recent log entries in chronological order, as opposed to in order of recency
            return_lines.append(entry.message_content)

        await send_lines(message.channel, return_lines, code_mode=True)
        self.bot_log.info("sent audit log to user {} (id: {}) based on (num_entries: {}, search_term: {})".format(message.author.name, message.author.id, num_entries, search_term))
        return None


    async def help(self, _, message, command_args, session):
        if len(command_args) == 0:
            commands = [keyword for keyword in self.command_dict]
            commands.sort() # alphabetize list so it's easier to find specific commands
            message_lines = ["Must run {}help with a specific command! Here's a list of commands:".format(self.command_prefix)] + commands
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
