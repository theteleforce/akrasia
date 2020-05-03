from database_utils import AuditLogEntry, get_or_init_user

class Logger: # kept as class for backwards compatability
    def __init__(self):
        pass

    @staticmethod
    def log(client, message, session):
        user = get_or_init_user(client, message, session)
        message_content = "[{}] {} (id: {}) | {}".format(message.created_at.strftime("%m/%d/%Y %I:%M:%S %p"), message.author.name, message.author.id, message.content)
        session.add(AuditLogEntry(message_id=message.id, user=user, guild_id=message.guild.id if message.guild is not None else user.id, message_content=message_content, timestamp=message.created_at))
        session.commit() # have to commit here; otherwise, errors would cause this log entry to be rolled back in handle_command, which is the opposite of what we want
