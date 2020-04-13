import constants as c
import datetime as dt

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
BaseTable = declarative_base()

class Server(BaseTable):
    __tablename__ = "servers"

    id = Column(Integer, primary_key=True)
    name = Column(String)
    last_quotes_time = Column(DateTime)


class Role(BaseTable):
    __tablename__ = "roles"

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    server_id = Column(Integer, ForeignKey("servers.id"), index=True)
    server = relationship("Server", back_populates="roles")


class User(BaseTable):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String, index=True)
    main_server_id = Column(Integer, ForeignKey("servers.id"))
    main_server = relationship("Server", back_populates="users_with_main_server")
    last_test_avatar_time = Column(DateTime)

class Reminder(BaseTable):
    __tablename__ = "reminders"

    id = Column(Integer, primary_key=True)
    message = Column(String)
    send_at = Column(DateTime)
    user_id = Column(Integer, index=True)
    failures = Column(Integer)

class Alias(BaseTable):
    __tablename__ = "aliases"

    id = Column(Integer, primary_key=True)
    alias = Column(String, index=True)
    true_function = Column(String)
    server_id = Column(Integer, ForeignKey("servers.id"))
    server = relationship("Server", back_populates="aliases")

class Quote(BaseTable):
    __tablename__ = "quotes"

    image_url = Column(String, primary_key=True)
    server_id = Column(Integer, ForeignKey("servers.id"))
    user_ids = Column(String, index=True)
    text = Column(String(length=1000), index=True)
    server = relationship("Server", back_populates="quotes")


def init_databases(engine):
    Server.roles = relationship("Role", order_by=Role.id, back_populates="server")
    Server.users_with_main_server = relationship("User", order_by=User.id, back_populates="main_server")
    Server.aliases = relationship("Alias", order_by=Alias.id, back_populates="server")
    Server.quotes = relationship("Quote", back_populates="server")
    BaseTable.metadata.create_all(engine)


async def setup(message, _, session, log, doesnt_exist=False):
    if message.guild is None:
        return "Can't call setup in a DM!" # flat-out return here since there's no point in contacting the database
    server_id = message.guild.id

    if not doesnt_exist:
        try:
            existing_db_entry = session.query(Server).filter(Server.id == server_id).first()
        except Exception as e:
            log.error("Failed to query database for server with ID {}: {}".format(server_id, e))
            raise e
        if existing_db_entry is not None:
            await message.channel.send("Setup has already been run on this server!")
            raise Exception()

    try:
        session.add(Server(id=server_id, name=message.guild.name, last_quotes_time=dt.datetime.now() - dt.timedelta(seconds=c.QUOTES_COOLDOWN)))
    except Exception as e:
        log.error("Failed to add row to Servers for server {} (id: {}); error was {}".format(message.guild.name, server_id, e))
        raise e

    log.info("Successfully ran setup for server {} (id: {})".format(message.guild.name, server_id))
    return "Setup successful!"


async def get_or_init_server(client, message, session):
    server = session.query(Server).filter(Server.id == message.guild.id).first()
    if server is None:
        try:
            server = Server(id=message.guild.id, name=message.guild.name, last_quotes_time=dt.datetime.now() - dt.timedelta(seconds=c.QUOTES_COOLDOWN))
            session.add(server)
            client.bot_log.info("Successfully added server {} (id: {}) to database".format(message.guild.name, message.guild.id))
        except Exception as e:
            client.bot_log.error("Failed to add row to Servers for server {} (id: {}); error was {}".format(message.guild.name, message.guild.id, e))
            raise e

    return server


async def get_or_init_user(client, message, session):
    user = session.query(User).filter(User.id == message.author.id).first()
    if user is None:
        try:
            user = User(id=message.author.id, name=message.author.name, last_test_avatar_time=dt.datetime.now() - dt.timedelta(seconds=c.AVATAR_TEST_COOLDOWN))
            session.add(user)
            client.bot_log.info("Successfully added user {} (id: {}) to database".format(message.author.name, message.author.id))
        except Exception as e:
            client.bot_log.error("Failed to add row to Users for user {} (id: {}); error was {}".format(message.author.name, message.author.id, e))
            raise e

    return user
