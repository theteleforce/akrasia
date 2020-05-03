import constants as c
import sqlalchemy as db

from database_utils import Role, get_or_init_server

async def add_role(client, message, command_args, session):
    if message.guild is None:
        return c.GUILD_REQUIRED_MESSAGE.format(client.command_prefix, "addrole", client.command_prefix)

    if not message.author.guild_permissions.manage_roles:
        client.bot_log.warning("User {} (id: {}) called !addrole {} without manage role permissions on server {} (id: {})!".format(
            message.author.name, message.author.id, command_args, message.guild.name, message.guild.id))
        return "You don't have permissions to edit roles!"

    if command_args is None:
        return "No role given!"
    role_name = " ".join(command_args)

    server_roles = [role for role in message.guild.roles if role.name.lower() == role_name.lower()]
    if len(server_roles) != 0:
        client.bot_log.info("Didn't add role {} to server {} (id: {}) because such a role already existed".format(role_name, message.guild.name, message.guild.id))
        return "A role with that name exists on this server!"

    db_role_already_exists = session.query(Role).filter(db.and_(Role.server_id == message.guild.id, Role.name == role_name.lower())).first()
    if db_role_already_exists is not None:
        client.bot_log.info("Didn't add role {} to server {} (id: {}) because the role was already in the database".format(role_name, message.guild.name, message.guild.id))
        return "That role is already in the database! (you can delete it from both the server and database using !deleterole)"

    try:
        new_role = await message.guild.create_role(name=role_name, mentionable=True, reason="Added via Akrasia by {} (id: {})".format(message.author.name, message.author.id))
    except Exception as e:
        client.bot_log.warning("Failed to add role {} (id: {}) to server {} (id: {}); error was {}".format(server_roles[0].name, server_roles[0].id, message.guild.name, message.guild.id, e))
        return "Couldn't add that role (do I need permissions?)"

    server = get_or_init_server(client, message.guild, session)
    session.add(Role(id=new_role.id, name=role_name.lower(), server=server))
    client.bot_log.info("Added role {} (id: {}) to sever {} (id: {})".format(new_role.name, new_role.id, message.guild.name, message.guild.id))
    return "Added role `{}`!".format(role_name)


async def delete_role(client, message, command_args, session):
    if message.guild is None:
        return c.GUILD_REQUIRED_MESSAGE.format(client.command_prefix, "deleterole", client.command_prefix)

    if not message.author.guild_permissions.manage_roles:
        client.bot_log.warning("User {} (id: {}) called !deleterole {} without manage role permissions on server {} (id: {})!".format(message.author.name, message.author.id, command_args, message.guild.name, message.guild.id))
        return "You don't have permissions to edit roles!"

    if command_args is None:
        return "No role given!"
    role_name = " ".join(command_args).lower()

    server_roles = [role for role in message.guild.roles if role.name.lower() == role_name]
    if len(server_roles) == 0:
        client.bot_log.info("Didn't delete role {} from server {} (id: {}) because no such role existed".format(role_name, message.guild.name, message.guild.id))
        return "No role with that name exists on this server!"
    role_to_delete = server_roles[0]

    db_role_to_delete = session.query(Role).filter(db.and_(Role.server_id == message.guild.id, Role.name == role_name)).first()
    if db_role_to_delete is not None:
        session.delete(db_role_to_delete)
        client.bot_log.info("Deleted role {} from database on server {} (id: {})".format(role_name, message.guild.name, message.guild.id))
    else:
        client.bot_log.info("Didn't delete role {} from database on server {} (id: {}) because the role wasn't in the database".format(role_name, message.guild.name, message.guild.id))

    try:
        await role_to_delete.delete(reason="Deleted via Akrasia by {} (id: {})".format(message.author.name, message.author.id))
    except Exception as e:
        client.bot_log.warning("Failed to delete role {} (id: {}) from server {} (id: {}); error was {}".format(server_roles[0].name, server_roles[0].id, message.guild.name, message.guild.id, e))
        return "Couldn't remove that role (do I need permissions?)"

    client.bot_log.info("Deleted role {} (id: {}) from sever {} (id: {})".format(role_to_delete.name, role_to_delete.id, message.guild.name, message.guild.id))
    return "Deleted role `{}`!".format(role_name)


async def unlist_role(client, message, command_args, session):
    if message.guild is None:
        return c.GUILD_REQUIRED_MESSAGE.format(client.command_prefix, "unlistrole", client.command_prefix)

    if not message.author.guild_permissions.manage_roles:
        client.bot_log.warning("User {} (id: {}) called !unlistrole {} without manage role permissions on server {} (id: {})!".format(message.author.name, message.author.id, command_args, message.guild.name, message.guild.id))
        return "You don't have permissions to edit roles!"

    if command_args is None:
        return "No role given!"
    role_name = " ".join(command_args).lower()
    db_role_to_delete = session.query(Role).filter(db.and_(Role.server_id == message.guild.id, Role.name == role_name)).first()
    if db_role_to_delete is not None:
        session.delete(db_role_to_delete)
        client.bot_log.info("Unlisted role {} (id: {}) from sever {} (id: {})".format(db_role_to_delete.name, db_role_to_delete.id, message.guild.name, message.guild.id))
        return "Role can no longer be joined with !join."
    else:
        client.bot_log.info("Didn't unlist role {} from server {} (id: {}) because the role wasn't in the database".format(role_name, message.guild.name, message.guild.id))
        return "That role wasn't in the database! (so it wasn't !join-able in the first place)."


async def leave_role(client, message, command_args, __):
    if message.guild is None:
        return c.GUILD_REQUIRED_MESSAGE.format(client.command_prefix, "leave", client.command_prefix)

    if command_args is None:
        return "No role given!"
    role_name = " ".join(command_args)

    server_roles = [role for role in message.guild.roles if role.name.lower() == role_name.lower()]
    if len(server_roles) == 0:
        return "No such role exists on this server!"

    user_roles = [role for role in message.author.roles if role.name.lower() == role_name.lower()]
    if len(user_roles) == 0:
        return "You don't have that role!"

    try:
        await message.author.remove_roles(server_roles[0], reason="Removed via Akrasia")
    except Exception as e:
        client.bot_log.warning("Failed to remove role {} (id: {}) from user {} (id: {}) in server {} (id: {}); error was {}".format(server_roles[0].name, server_roles[0].id, message.author.name, message.author.id, message.guild.name, message.guild.id, e))
        return "Couldn't remove you from that role (do I need permissions?)"

    client.bot_log.info("Removed role {} (id: {}) from user {} (id: {}) in sever {} (id: {})".format(server_roles[0].name, server_roles[0].id, message.author.name, message.author.id, message.guild.name, message.guild.id))
    return "Removed from role `{}`.".format(server_roles[0].name)


async def join_role(client, message, command_args, session):
    if message.guild is None:
        return c.GUILD_REQUIRED_MESSAGE.format(client.command_prefix, "join", client.command_prefix)

    if command_args is None:
        return "No role given!"
    role_name = " ".join(command_args).lower()

    server_roles = [role for role in message.guild.roles if role.name.lower() == role_name]
    if len(server_roles) == 0:
        return "No such role exists on this server!"

    user_roles = [role for role in message.author.roles if role.name.lower() == role_name]
    if len(user_roles) > 0:
        return "You already have that role!"

    role_in_server = session.query(Role).filter(db.and_(Role.server_id == message.guild.id, Role.name == role_name)).first()
    if role_in_server is None:
        client.bot_log.error("Failed to add role {} (id: {}) to user {} (id: {}) in server {} (id: {}); role was not bot-addable.".format(server_roles[0].name, server_roles[0].id, message.author.name, message.author.id, message.guild.name, message.guild.id))
        return "That role is not !join-able."

    try:
        await message.author.add_roles(server_roles[0], reason="Joined via Akrasia")
    except Exception as e:
        client.bot_log.error("Failed to add role {} (id: {}) to user {} (id: {}) in server {} (id: {}); error was {}".format(server_roles[0].name, server_roles[0].id, message.author.name, message.author.id, message.guild.name, message.guild.id, e))
        return "Couldn't add you to that role (do I need permissions?)"

    client.bot_log.info("Added role {} (id: {}) to user {} (id: {}) in sever {} (id: {})".format(server_roles[0].name, server_roles[0].id, message.author.name, message.author.id, message.guild.name, message.guild.id))
    return "Added to role `{}`.".format(server_roles[0].name)


async def list_role(client, message, command_args, session):
    if message.guild is None:
        return c.GUILD_REQUIRED_MESSAGE.format(client.command_prefix, "listrole", client.command_prefix)

    if command_args is None:
        return "No role given!"
    role_name = " ".join(command_args).lower()

    server_roles = [role for role in message.guild.roles if role.name.lower() == role_name]
    if len(server_roles) == 0:
        return "No such role exists on this server!"
    role = server_roles[0]

    role_in_server = session.query(Role).filter(db.and_(Role.server_id == message.guild.id, Role.name == role_name)).first()
    if role_in_server is None:
        client.bot_log.error("Failed to list role {} (id: {}) in server {} (id: {}); role was not bot-addable.".format(server_roles[0].name, server_roles[0].id, message.author.name, message.author.id, message.guild.name, message.guild.id))
        return "That role is not !join-able, and thus cannot be listed."

    members_list = [member.display_name for member in role.members]
    if len(members_list) == 0:
        return "That role is empty!"
    members_list.sort()

    client.bot_log.info("Listing members of role {} to user {} (id: {}) in server {} (id: {})".format(role.name, message.author.name, message.author.id, message.guild.name, message.guild.id))
    return "Members of {}:\n{}".format(role.name, ", ".join(members_list))


roles_module = {
    "addrole": (add_role, "**addrole** *[role name]*\n"
                          "*Permissions needed: manage roles*\n"
                          "    Adds the given role to the server, and allows users to join it using !join.\n"
                          "    `!addrole goon platoon` adds the role \"goon platoon\" to the server."),
    "deleterole": (delete_role, "**deleterole** *[role name]*\n"
                                "*Permissions needed: manage roles*\n"
                                "    Deletes the given role from the server.\n"
                                "    `!deleterole goon platoon` deletes the role \"goon platoon\" from the server."),
    "unlistrole": (unlist_role, "**unlistrole** *[role name]*\n"
                                "*Permissions needed: manage roles*\n"
                                "    Stops users from joining the role with !join, but leaves the role intact.\n"
                                "    `!unlist role goon platoon` prevents users from joining \"goon platoon\" via !join."),
    "join": (join_role, "**join** *[role name]*\n"
                        "*Permissions needed: none*\n"
                        "    Joins the given role, if it's been added with !addrole.\n"
                        "    `!join goon platoon` joins the role \"goon platoon\""),
    "leave": (leave_role, "**leave** *[role name]*\n"
                          "*Permissions needed: none*\n"
                          "    Leaves the given role.\n"
                          "    `!leave goon platoon` leaves the role \"goon platoon\""),
    "listrole": (list_role, "**listrole** *[role name]*\n"
                            "*Permissions needed: none*\n"
                            "    Lists all users with a given role, if that role is !join-able.\n"
                            "    `!list goon platoon` lists all players with the role \"goon platoon\"")
}
