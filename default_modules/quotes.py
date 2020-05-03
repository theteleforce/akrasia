import sqlalchemy as db

from database_utils import Quote, get_or_init_server, get_or_init_user
from discord import File
from discord.errors import HTTPException
from message_utils import send_lines, get_time_text
from multiprocessing.pool import ThreadPool
from random import choice

# Asynchronous (Discord) functions
async def quote(client, message, command_args, session):
    if not message.author.guild_permissions.administrator:
        return "You don't have permissions to run that command! (required permissions: administrator)"

    if message.guild is None:
        return c.GUILD_REQUIRED_MESSAGE.format(client.command_prefix, "quote", client.command_prefix)

    if len(command_args) < 3:  # if the command might've been !quote [message id] or !quote [message id] #
        try:
            first_message = await message.channel.fetch_message(command_args[0])
            messages = [first_message]

            if len(command_args) == 2:
                n_messages = int(command_args[1])

                if n_messages > 10:
                    client.bot_log.info("Failed to add quote in {} (id: {}); quote was over 10 messages".format(message.guild.name, message.guild.id))
                    return "Quotes are limited at 10 messages!"
                elif n_messages > 1:
                    next_messages = await message.channel.history(limit=(n_messages - 1), after=first_message.created_at).flatten()
                    messages.extend(next_messages)

            quote_img = make_quote(messages, message.guild)
            quote_img_link = await __upload_quote(client, message.guild.id, quote_img)
            return await __add_quote_to_database(client, message, messages, quote_img_link, session)
        except HTTPException:  # this means the first word wasn't a message ID; we can still try to find it in word search
            pass
        except ValueError:  # this means the first word wasn't an ID or the second word wasn't a number; we can still try to find it in word search
            pass

    # if we've gotten to this point, we have to try to find the quote with reverse search
    n_messages = 1
    try:
        n_messages = int(command_args[-1])
        search_string = " ".join(command_args[:-1])
        if n_messages > 10:
            return "Quotes are limited at 10 messages!"
    except:
        search_string = " ".join(command_args)

    matching_message = await message.channel.history(limit=c.MAX_REVERSE_SEARCH_MESSAGES,
                                                     before=message.created_at).find(
        lambda m: search_string in m.clean_content)
    if matching_message is None:
        client.bot_log.info("Failed to add quote in {} (id: {}); no messages matching the given identifier '{}'".format(
            message.guild.name, message.guild.id, search_string))
        return "Couldn't find a message with the identifier {}(note that messages more than {} messages away must be quoted via ID)".format(
            search_string, c.MAX_REVERSE_SEARCH_MESSAGES)

    messages = [matching_message]
    if n_messages > 1:
        next_messages = await message.channel.history(limit=(n_messages - 1),
                                                      after=matching_message.created_at).flatten()
        messages.extend(next_messages)

    quote_img = make_quote(messages, message.guild)
    quote_img_link = await __upload_quote(client, message.guild.id, quote_img)

    return await __add_quote_to_database(client, message, messages, quote_img_link, session)


async def __add_quote_to_database(client, message, messages, quote_img_link, session):
    users_in_quote = set([str(m.author.id) for m in messages])
    text_in_quote = ""
    for m in messages:
        if m.clean_content is not None and len(m.clean_content) > 0:
            text_in_quote += m.clean_content
    user_id_string = " ".join(users_in_quote)
    try:
        server = await get_or_init_server(client, messages[0].guild, session)
        if len(server.quotes) > c.MAX_QUOTES_PER_SERVER:
            await message.channel.send(
                "Maximum number of quotes per server exceeded ({})! To increase your maximum, please contact `SyIvan#1334` via PMs.".format(
                    c.MAX_QUOTES_PER_SERVER))
            raise Exception("max number of quotes exceeded")
        session.add(Quote(image_url=quote_img_link, user_ids=user_id_string, text=text_in_quote, server=server))
    except Exception as e:
        raise Exception(
            "Created quote on server {} (id: {}), but couldn't add it to database: {}".format(messages[0].guild.name,
                                                                                              messages[0].guild.id, e))
    client.bot_log.info("Added quote in {} (id: {})".format(messages[0].guild.name, messages[0].guild.id))
    return "Quote added!\n{}".format(quote_img_link)


async def __upload_quote(client, server_id, quote_img):
    home_server = client.get_guild(c.HOME_SERVER_ID)
    server_quote_channel = [channel for channel in home_server.text_channels if channel.name == str(server_id)]
    if len(server_quote_channel) == 0:
        server_quote_channel = await home_server.create_text_channel(str(server_id))
    else:
        server_quote_channel = server_quote_channel[0]

    with BytesIO() as file_buffer:
        quote_img.save(file_buffer, format="png")
        file_buffer.seek(0)  # reset the pointer to the beginning so we don't send 0 bytes
        msg_with_file = await server_quote_channel.send(file=File(file_buffer, filename="quote.png"))
    return msg_with_file.attachments[0].url


async def get_quote(client, message, command_args, session):
    if message.guild is None:
        return c.GUILD_REQUIRED_MESSAGE.format(client.command_prefix, "getquote", client.command_prefix)
    server = await get_or_init_server(client, message.guild, session)

    relevant_quotes, error = await __search_quotes(client, message.guild, server, command_args, only_one=True)
    if error is not None and error != c.AMBIGUOUS_ERROR: # ambiguity is fine here; we just send one of the ambiguous quotes
        await message.channel.send(error)
    else:
        await message.channel.send(choice(relevant_quotes).image_url)


async def delete_quote(client, message, command_args, session):
    if message.guild is None:
        return c.GUILD_REQUIRED_MESSAGE.format(client.command_prefix, "deletequote", client.command_prefix)

    if not message.author.guild_permissions.administrator:
        return "You don't have permissions to run that command! (required permissions: administrator)"

    server = await get_or_init_server(client, message.guild, session)

    if len(command_args) == 1 and command_args[0][
                                  :39] == "https://cdn.discordapp.com/attachments/":  # before text searching, try to remove the quote by URL
        matching_quote = session.query(Quote).filter(
            db.and_(Quote.server_id == message.guild.id, Quote.image_url == command_args[0])).first()
        if matching_quote is None:
            client.bot_log.info("couldn't find a quote to delete in server {} (id: {}) with url {}".format(message.guild.name, message.guild.id, command_args[0]))
            return "Couldn't find a quote at that URL!"
        else:
            client.bot_log.info("deleted a quote in server {} (id: {}) with url {}".format(message.guild.name, message.guild.id, command_args[0]))
            session.delete(matching_quote)
            return "Quote deleted!"

    relevant_quotes, error = await __search_quotes(client, message.guild, server, command_args, only_one=True)
    if error is not None:
        if error == c.AMBIGUOUS_ERROR:
            return "\n".join(["Ambiguous text search term. Found {} results:".format(len(relevant_quotes))] + [rquote.image_url for rquote in relevant_quotes])
        else:
            await message.channel.send(error)
    else:
        client.bot_log.info("Successfully deleted quote with id {} from server {} (id: {})".format(relevant_quotes[0].id, message.guild.name, message.guild.id))
        session.delete(relevant_quotes[0])
        return "Quote deleted!"


async def get_quotes(client, message, command_args, session):
    if message.guild is None:
        return c.GUILD_REQUIRED_MESSAGE.format(client.command_prefix, "getquotes", client.command_prefix)

    server = await get_or_init_server(client, message.guild, session)
    remaining_cooldown_time = c.QUOTES_COOLDOWN - (dt.datetime.now() - server.last_quotes_time).total_seconds()
    if remaining_cooldown_time > 0:
        return "Quotes is on cooldown (try again in {} seconds!)".format(remaining_cooldown_time)

    relevant_quotes, error = await __search_quotes(client, message.guild, server, command_args)
    if error is not None:
        await message.channel.send(error)
    else:
        server.last_quotes_time = dt.datetime.now()
        return "\n".join([rquote.image_url for rquote in relevant_quotes])


async def __search_quotes(client, guild, server, command_args, only_one=False):
    if len(command_args) == 0:
        if len(server.quotes):
            client.bot_log.info("Returning all quotes on server {} (id: {}) to parameter-less quote search".format(server.name, server.id))
            return server.quotes, None
        else:
            client.bot_log.info("Couldn't list quotes for server {} (id: {}) because it doesn't have any".format(server.name, server.id))
            return None, "No quotes exist on this server!"
    user_search_string = command_args[0]
    text_search_string = " ".join(command_args[1:]) if len(command_args) > 1 else None
    client.bot_log.info("searching for quotes on server {} (id: {}) with search params (user: {}, text: {})".format(server.name, server.id, user_search_string, text_search_string))
    # first, try to search for user by ID, then user by name, then user by nickname
    try:  # note that this allows searching by user ID for quotes from users who've since left the server
        relevant_quotes = [rquote for rquote in server.quotes if user_search_string in rquote.user_ids]
        if text_search_string:
            relevant_quotes = [rquote for rquote in relevant_quotes if text_search_string in rquote.text]

        if len(relevant_quotes):
            client.bot_log.info("Found quotes matching the parameters (user id: {}, text: {}) on server {} (id: {})".format(
                user_search_string, text_search_string, server.name, server.id))
            return relevant_quotes, None
        else:
            client.bot_log.info("No quotes found matching the parameters (user id: {}, text: {}) on server {} (id: {})".format(
                user_search_string, text_search_string, server.name, server.id))
    except:  # if we couldn't parse the search string as an ID or find the user by that int, no problem
        pass

    # search users first by username
    relevant_users = [user for user in guild.members if user_search_string.lower() in user.name.lower()]
    if len(relevant_users) > 1:
        client.bot_log.info(
            "Didn't fetch quote for the parameters (user name: {}, text: {}) on server {} (id: {}); ambiguous params".format(
                user_search_string, text_search_string, server.name, server.id))
        return "Ambiguous user. Did you mean:" + "\n".join(
            ["{} (nickname: {}, id: {})".format(user.name, user.nick, user.id) for user in relevant_users])
    elif len(relevant_users) == 1:
        relevant_quotes = [rquote for rquote in server.quotes if str(relevant_users[0].id) in rquote.user_ids]
        if text_search_string:
            relevant_quotes = [rquote for rquote in relevant_quotes if text_search_string in rquote.text]

        if len(relevant_quotes):
            if len(relevant_quotes) > 1 and only_one:
                client.bot_log.info(
                    "Failed to find single quote matching the parameters (user name: {}, text: {}) on server {} (id: {})".format(
                        user_search_string, text_search_string, server.name, server.id))
                return relevant_quotes, c.AMBIGUOUS_ERROR
            else:
                client.bot_log.info("Found quotes matching the parameters (user name: {}, text: {}) on server {} (id: {})".format(
                    user_search_string, text_search_string, server.name, server.id))
                return relevant_quotes, None
        else:
            client.bot_log.info("No quotes found matching the parameters (user name: {}, text: {}) on server {} (id: {})".format(
                user_search_string, text_search_string, server.name, server.id))

    # if no users were found, fall back to nickname search
    relevant_users = [user for user in guild.members if user_search_string.lower() in user.display_name.lower()]
    if len(relevant_users) > 1:
        client.bot_log.info(
            "Didn't fetch quote for the parameters (user nick: {}, text: {}) on server {} (id: {}); ambiguous params".format(
                user_search_string, text_search_string, server.name, server.id))
        return "Ambiguous user. Did you mean:" + "\n".join(
            ["{} (nickname: {}, id: {})".format(user.name, user.nick, user.id) for user in relevant_users])
    elif len(relevant_users) == 1:
        relevant_quotes = [rquote for rquote in server.quotes if str(relevant_users[0].id) in rquote.user_ids]
        if text_search_string:
            relevant_quotes = [rquote for rquote in relevant_quotes if text_search_string in rquote.text]
        if len(relevant_quotes):
            client.bot_log.info("Found quotes matching the parameters (user nick: {}, text: {}) on server {} (id: {})".format(
                user_search_string, text_search_string, server.name, server.id))
            return relevant_quotes, None
        else:
            client.bot_log.info("No quotes found matching the parameters (user nick: {}, text: {}) on server {} (id: {})".format(
                user_search_string, text_search_string, server.name, server.id))

    # if still no users were found, bunch the user search string in with the text search as a last resort
    old_text_search_string = text_search_string
    if text_search_string is not None:
        text_search_string = user_search_string + " " + text_search_string
    else:
        text_search_string = user_search_string
    relevant_quotes = [rquote for rquote in server.quotes if text_search_string.lower() in rquote.text.lower()]
    if len(relevant_quotes):
        client.bot_log.info("Found last-resort quotes matching the parameters (text: {}) on server {} (id: {})".format(
            text_search_string, server.name, server.id))
        return relevant_quotes, None
    else:
        client.bot_log.info(
            "No quotes of any kind found matching the parameters (user: {}, text: {}) on server {} (id: {})".format(
                user_search_string, text_search_string, server.name, server.id))
        return None, "No quotes found matching the parameters (user: {}, text: {}) or (text: {}). Try using some broader search terms!\n\n(note: if you specified a user, we couldn't find them on this server either)".format(
            user_search_string, old_text_search_string, text_search_string)

async def test_avatar(client, message, __, session):
    avatar_url = None
    if len(message.attachments):
        avatar_url = message.attachments[0].url if message.attachments[0].url.split(".")[-1] in c.SUPPORTED_IMAGE_FILETYPES else None
    elif len(message.embeds):
        avatar_url = message.embeds[0].thumbnail.proxy_url if (message.embeds[0].thumbnail is not None and message.embeds[0].thumbnail.proxy_url.split(".")[-1] in c.SUPPORTED_IMAGE_FILETYPES) else None

    if avatar_url is None:
        client.bot_log.info("failed to preview avatar for user {} (id: {}); no or unsupported attachment".format(message.author.name, message.author.id))
        return "Must include an attachment or embed of an image of one of these filetypes: {}\n\nNote that linking the image doesn't always work, but uploading it does.".format(c.SUPPORTED_IMAGE_FILETYPES)

    user = get_or_init_user(client, message, session)
    cooldown_time_remaining = c.AVATAR_TEST_COOLDOWN - (dt.datetime.now() - user.last_test_avatar_time).total_seconds()
    if cooldown_time_remaining > 0:
        client.bot_log.info("failed to preview avatar at {} for user {} (id: {}); {} seconds left on cooldown time".format(avatar_url, message.author.name, message.author.id, cooldown_time_remaining))
        return "You tested another avatar too recently (try again in {} seconds)".format(cooldown_time_remaining)

    test_img = avatar_test_message(message.author.display_name, avatar_url, dt.datetime.now(), choice(c.AVATAR_TEST_MESSAGES))
    with BytesIO() as file_buffer:
        test_img.save(file_buffer, format="png")
        file_buffer.seek(0) # reset the pointer to the beginning so we don't send 0 bytes
        await message.channel.send(file=File(file_buffer, filename="avatar_test.png"))
    client.bot_log.info("previewed avatar at {} for user {} (id: {});".format(avatar_url, message.author.name, message.author.id))
    user.last_test_avatar_time = dt.datetime.now()

# Synchronous (client-side) functions
import datetime as dt
import requests
import os
import constants as c

from discord import Attachment, Embed
from io import BytesIO
from PIL import Image, ImageChops, ImageDraw, ImageFont


class TestMessage: # imitates discord.Message for !testavatar
    def __init__(self, author_name, avatar_url, created_at, clean_content):
        self.id = 1 # only one of these will be in draw_quote() at a time, so this is safe
        self.author = TestAuthor(author_name, avatar_url)
        self.created_at = created_at
        self.clean_content = clean_content
        self.attachments = []
        self.embeds = []


class TestAuthor:
    def __init__(self, display_name, avatar_url):
        self.display_name = display_name
        self.avatar_url = avatar_url


def avatar_test_message(author_name, avatar_url, created_at, clean_content):
    headers_response = requests.head(avatar_url)
    if int(headers_response.headers.get("content-length", c.MAX_AVATAR_FILESIZE + 1)) > c.MAX_AVATAR_FILESIZE:
        return "Avatar filesize is too big!"

    messages = [TestMessage(author_name, avatar_url, created_at, clean_content)]
    return make_quote(messages, None, store_avatar=False)


def make_quote(messages, _, store_avatar=True):
    """quote_is_possible, error = ensure_quote(server, messages[0].id, len(messages))
    if not quote_is_possible:
        return error"""

    quote_img_size, quote_imgs, fonts = parse_quote(messages)
    return draw_quote(messages, quote_img_size, quote_imgs, fonts, store_avatar)

def parse_quote(messages):
    now = dt.datetime.now() # used for timestamping messages relative to when they're quoted
    name_font, timestamp_font, content_font = load_fonts()
    last_user_to_talk = None
    last_message = None
    image_objects = []
    image_size = [c.DEFAULT_LEFT_MARGIN + c.PFP_DIAMETER + c.PFP_TO_TEXT_MARGIN, c.DEFAULT_V_MARGIN - c.BETWEEN_AUTHORS_MARGIN] # when we set the first last_user_to_talk, this will make the initial vertical offset = c.BEGINNING_TOP_OFFSET
    for message in messages:
        if len(message.attachments) > 2: # hard cap attachments and embeds at 2 so my hard drive doesn't blow up
            message.attachments = message.attachments[:2]
        if len(message.embeds) > 2:
            message.attachments = message.embeds[:2]

        if message.author != last_user_to_talk or (message.created_at - last_message.created_at).total_seconds() > c.SECONDS_FOR_SEPERATED_MESSAGES:
            last_user_to_talk = message.author
            image_size[1] += c.BETWEEN_AUTHORS_MARGIN + c.AUTHOR_SIZE + c.NAME_TO_MESSAGE_MARGIN # switching authors has the effect of adding another c.BETWEEN_MESSAGES_MARGIN
            name_plus_timestamp_width = name_font.getsize(message.author.display_name)[0] + timestamp_font.getsize(get_time_text(message.created_at, now))[0]
        else:
            name_plus_timestamp_width = 0 # no need to calculate this again if we adjusted for it in this user's first message

        for attachment_or_embed in (message.attachments + message.embeds):
            image_objects.append(DiscordImage(attachment_or_embed, message.id))

        if len(message.clean_content) > 0:
            content_width = content_font.getsize(message.clean_content)[0]
        else:
            content_width = 0
        message_width = max(name_plus_timestamp_width, content_width)
        if message_width > image_size[0]:
            if message_width > c.MAX_CONTENT_WIDTH:
                image_size[0] = c.MAX_CONTENT_WIDTH
            else:
                image_size[0] = message_width

        if message.clean_content is not None and len(message.clean_content) > 0:
            text_lines = len(wrap_text(message.clean_content, content_font, c.MAX_CONTENT_WIDTH))
            image_size[1] += text_lines * (c.MESSAGE_SIZE + c.BETWEEN_LINES_MARGIN)
        image_size[1] += c.BETWEEN_MESSAGES_MARGIN

        last_message = message

    image_threadpool = ThreadPool()
    image_threadpool.map(lambda i: i.fetch_image(), image_objects)
    image_threadpool.close()

    images = {}
    for image_object in [i for i in image_objects if i.image is not None]:
        if image_object.message_id in images:
            images[image_object.message_id] += [image_object.image]
        else:
            images[image_object.message_id] = [image_object.image]

        image_size[0] = max(image_size[0], image_object.image.size[0])
        image_size[1] += image_object.image.size[1] + c.BETWEEN_LINES_MARGIN
    image_size[0] += c.DEFAULT_LEFT_MARGIN + c.PFP_DIAMETER + c.PFP_TO_TEXT_MARGIN + c.DEFAULT_RIGHT_MARGIN # set this afterwards so we can do image_size[0] > c.MAX_CONTENT_WIDTH comparisons earlier
    image_size[1] += c.DEFAULT_V_MARGIN # add bottom margin
    return (image_size[0], image_size[1]), images, {"name": name_font, "timestamp": timestamp_font, "content": content_font}


def draw_quote(messages, image_size, images, fonts, store_avatar):
    background = Image.new("RGBA", image_size, c.BACKGROUND_COLOR)
    background_draw = ImageDraw.Draw(background)

    now = dt.datetime.now() # used for timestamping messages relative to when they're quoted
    last_message = None
    last_user_to_talk = None
    vertical_offset = c.DEFAULT_V_MARGIN - c.BETWEEN_AUTHORS_MARGIN # when we set the first last_user_to_talk, this will make the initial vertical offset = c.DEFAULT_V_MARGIN

    for message in messages:
        if message.author != last_user_to_talk or (message.created_at - last_message.created_at).total_seconds() > c.SECONDS_FOR_SEPERATED_MESSAGES:
            last_user_to_talk = message.author
            vertical_offset += c.BETWEEN_AUTHORS_MARGIN

            avatar_img = get_avatar_img(message.author, store_avatar)
            if avatar_img is not None: # sometimes we won't get the avatar for some reason; this is fine
                background.paste(avatar_img, (c.DEFAULT_LEFT_MARGIN, vertical_offset), avatar_img)

            background_draw.text((c.DEFAULT_LEFT_MARGIN + c.PFP_DIAMETER + c.PFP_TO_TEXT_MARGIN, vertical_offset), message.author.display_name, c.AUTHOR_COLOR, fonts["name"])
            background_draw.text((c.DEFAULT_LEFT_MARGIN + c.PFP_DIAMETER + c.PFP_TO_TEXT_MARGIN + fonts["name"].getsize(message.author.display_name)[0] + c.NAME_TO_TIMESTAMP_MARGIN, vertical_offset + c.TIMESTAMP_TOP_OFFSET), get_time_text(message.created_at, now), c.TIMESTAMP_COLOR, fonts["timestamp"])
            vertical_offset += c.AUTHOR_SIZE + c.NAME_TO_MESSAGE_MARGIN

        if message.clean_content is not None and len(message.clean_content) > 0:
            for line in wrap_text(message.clean_content, fonts["content"], c.MAX_CONTENT_WIDTH):
                background_draw.text((c.DEFAULT_LEFT_MARGIN + c.PFP_DIAMETER + c.PFP_TO_TEXT_MARGIN, vertical_offset), line, c.MESSAGE_COLOR, fonts["content"])
                vertical_offset += c.BETWEEN_LINES_MARGIN + c.MESSAGE_SIZE

        if len(message.attachments) or len(message.embeds):
            for image in images[message.id]:
                vertical_offset += c.TEXT_TO_IMAGE_MARGIN
                background.paste(image, (c.DEFAULT_LEFT_MARGIN + c.PFP_DIAMETER + c.PFP_TO_TEXT_MARGIN, vertical_offset), image)
                vertical_offset += image.size[1] + c.BETWEEN_LINES_MARGIN

        last_message = message

        vertical_offset += c.BETWEEN_MESSAGES_MARGIN

    return background


def ensure_quote(server, first_message_id, n_messages):
    server_quote_path = "{}/{}".format(c.QUOTES_DIR, server.id)
    if os.path.exists(server_quote_path):
        if len(os.listdir(server_quote_path)) > c.MAX_QUOTES_PER_SERVER:
            return False, "No space for quote (servers are limited to {} quotes maximum)".format(c.MAX_QUOTES_PER_SERVER)
        quote_path = "{}/{}_{}.png".format(server_quote_path, first_message_id, n_messages)
        if os.path.exists(quote_path):
            return False, "That quote already exists (you may delete it with !deletequote)"
        return True, None
    else:
        os.mkdir(server_quote_path)
        return True, None


def get_avatar_img(user, store_avatar):
    avatar_id = str(user.avatar_url).split("/")[-1].split("?")[0]
    avatar_path = "{}/{}".format(c.PFPS_FOLDER_PATH, avatar_id)
    if not os.path.exists(avatar_path):
        try:
            img_response = requests.get(user.avatar_url)
        except Exception as e:
            print("failed to get avatar (id: {}) from link: {}".format(avatar_id, e))
            return None

        base_avatar_img = Image.open(BytesIO(img_response.content)).convert("RGBA")
        avatar_img = circular_crop_avatar(base_avatar_img)
        if store_avatar:
            try:
                avatar_img.save(avatar_path)
            except Exception as e:
                print("failed to save avatar (id: {}) to file: {}".format(avatar_id, e))
        return avatar_img
    else:
        try:
            return Image.open(avatar_path)
        except Exception as e:
            print("failed to load avatar (id: {}) from file: {}".format(avatar_id, e))
            return None


def load_fonts():
    return ImageFont.truetype(c.DISCORD_BOLD_FONT, c.AUTHOR_SIZE), ImageFont.truetype(c.DISCORD_NORMAL_FONT, c.TIMESTAMP_SIZE), ImageFont.truetype(c.DISCORD_NORMAL_FONT, c.MESSAGE_SIZE)


def get_image(attachment_or_embed):
    if isinstance(attachment_or_embed, Attachment):
        if attachment_or_embed.filename.split(".")[-1] in c.SUPPORTED_IMAGE_FILETYPES:
            file_link = attachment_or_embed.url
        else:
            return None
    elif isinstance(attachment_or_embed, Embed):
        file_link = attachment_or_embed.thumbnail.url
    else:
        return None

    headers_response = requests.head(file_link)
    if int(headers_response.headers.get("content-length", c.MAX_EMBED_FILESIZE + 1)) > c.MAX_EMBED_FILESIZE:
        return None

    try:
        img_response = requests.get(file_link)
    except Exception as e:
        print("failed to get image from link: {}".format(e))
        return

    base_img = Image.open(BytesIO(img_response.content)).convert("RGBA")
    base_img.thumbnail(c.MAX_EMBED_DIMENSIONS, Image.ANTIALIAS)
    return base_img


def wrap_text(text, font, max_width):
    sentences = text.split("\n")
    words = []
    for sentence in sentences:
        words.extend(sentence.split(" "))
    lines = []

    current_line = ""
    for word in words:
        extended = current_line + " " + word if len(current_line) else word
        if font.getsize(extended)[0] > max_width or len(word) == 0 or word[-1] == "\n": # len(word) == 0 checks for consecutive newlines leaving an empty string in the words list
            lines.append(current_line)

            if font.getsize(word)[0] > max_width: # single words that are over the length limit are wrapped on a character-by-character basis
                word_lines = wrap_word(word, font, max_width)
                lines.extend(word_lines[:-1])
                current_line = word_lines[-1] # handles this bullshit: https://imgur.com/lrR1ItN
            else:
                current_line = word
        else:
            current_line = extended
    lines.append(current_line)

    return lines


def wrap_word(word, font, max_width):
    lines = []

    current_line = ""
    for character in word:
        extended = current_line + character
        if font.getsize(extended)[0] > max_width:
            lines.append(current_line)
            current_line = "{}".format(character) # don't convert it to a char type
        else:
            current_line = extended
    lines.append(current_line)

    return lines


def circular_crop_avatar(avatar_img):
    circle_mask = Image.open(c.PFP_MASK_PATH).convert("RGBA")
    if avatar_img.size != circle_mask.size:
        avatar_img = avatar_img.resize(circle_mask.size, Image.ANTIALIAS)

    cropped_avatar = ImageChops.multiply(circle_mask, avatar_img) # can't use standard .putalpha masks because it makes the visible parts of transparent avatars non-transparent
    return cropped_avatar


class DiscordImage:
    def __init__(self, attachment_or_embed, message_id):
        self.image = None
        self.message_id = message_id

        if isinstance(attachment_or_embed, Attachment):
            if attachment_or_embed.filename.split(".")[-1] in c.SUPPORTED_IMAGE_FILETYPES:
                self.url = attachment_or_embed.url
        elif isinstance(attachment_or_embed, Embed):
            self.url = attachment_or_embed.thumbnail.url
        else:
            self.url = None

    def fetch_image(self):
        headers_response = requests.head(self.url)
        if int(headers_response.headers.get("content-length", c.MAX_EMBED_FILESIZE + 1)) > c.MAX_EMBED_FILESIZE:
            self.image = None

        try:
            img_response = requests.get(self.url)
        except Exception as e:
            print("failed to get image from link: {}".format(e))
            return

        base_img = Image.open(BytesIO(img_response.content)).convert("RGBA")
        base_img.thumbnail(c.MAX_EMBED_DIMENSIONS, Image.ANTIALIAS)
        self.image = base_img


quote_module = {
    "quote": (quote, "**quote** *[message identifier] [# of messages]*\n"
                     "*quote [message identifier]*\n"
                     "*Permissions required: administrator*\n"
                     "    Adds a message or range of messages as a quote for this server.\n"
                     "    Quotes can be searched using !quote or !quotes.\n"
                     "    `!quote 699018254382923846` quotes the message with ID 699018254382923846\n"
                     "    `!quote 699018254382923846 2` quotes the message with ID 699018254382923846, and the one right after it\n"
                     "    `!quote body is buried at 2` quotes the last message with \"bodies are buried at\" in it, and the one right after it"),
    "deletequote": (delete_quote, "**deletequote** *[message identifier]*\n"
                                  "*deletequote [quote image link]*\n"
                                  "*Permissions required: administrator*\n"
                                  "    Removes a quote identified by its cdn.discordapp link or a search string from the server.\n"
                                  "    Quotes can be searched using !quote or !quotes.\n"
                                  "    `!removequote https://cdn.discordapp.com/attachments/698945685357199441/699133124617175070/quote.png` removes the quote stored at that link\n"
                                  "    `!removequote SyIvan body is buried at` removes the quote that has the string \"bodiy are buried at\" and the user SyIvan in it"
                                  "    `!removequote body is buried at` removes the quote with the string \"bodiy are buried at\""),
    "getquote": (get_quote, "**getquote** *[message identifier]*\n"
                            "*Permissions required: none*\n"
                            "    Retrieves a random quote from this server that matches the message identifier.\n"
                            "    `!getquote` retrieves a random quote from this server\n"
                            "    `!getquote SyIvan` retrieves a random quote with the user SyIvan from this server\n"
                            "    `!getquote SyIvan body is buried at` retrieves a random quote with the user SyIvan and the string \"body is buried at\" from this server."),
    "getquotes": (get_quotes, "**getquotes** *[message identifier]*\n"
                              "*Permissions required: none*\n"
                              "    Retrieves all quote from this server that match the message identifier.\n"
                              "    `!getquotes` retrieves all quotes from this server\n"
                              "    `!getquotes SyIvan` retrieves all quotes with the user SyIvan from this server\n"
                              "    `!getquotes SyIvan body is buried at` retrieves all quotes with the user SyIvan and the string \"body is buried at\" from this server."),
    "testavatar": (test_avatar, "**testavatar** *[avatar link or file]*\n"
                                "*Permissions required: none*\n"
                                "    Shows an image of the user saying something with the linked image as their avatar.\n"
                                "    Useful for testing avatar crops without getting ratelimited by Discord.\n"
                                "    `!testavatar https://i.imgur.com/Z1KRsdq.jpg` will show a message from the user with the avatar at the link\n"
                                "    `!testavatar with an image file attached will show a message from the user with that avatar")
}
