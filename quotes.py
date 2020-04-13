import datetime as dt
import pytz
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
    now = c.TIMEZONE.localize(dt.datetime.now()) # used for timestamping messages relative to when they're quoted
    name_font, timestamp_font, content_font = load_fonts()
    last_user_to_talk = None
    last_message = None
    images = {}
    image_size = [c.DEFAULT_LEFT_MARGIN + c.PFP_DIAMETER + c.PFP_TO_TEXT_MARGIN, c.BEGINNING_TOP_OFFSET - c.BETWEEN_AUTHORS_MARGIN] # when we set the first last_user_to_talk, this will make the initial vertical offset = c.BEGINNING_TOP_OFFSET
    for message in messages:
        if len(message.attachments) > 2: # hard cap attachments and embeds at 2 so my hard drive doesn't blow up
            message.attachments = message.attachments[:2]
        if len(message.embeds) > 2:
            message.attachments = message.embeds[:2]

        if message.author != last_user_to_talk or (message.created_at - last_message.created_at).total_seconds() > c.SECONDS_FOR_SEPERATED_MESSAGES:
            last_user_to_talk = message.author
            image_size[1] += c.BETWEEN_AUTHORS_MARGIN + c.AUTHOR_SIZE + c.NAME_TO_MESSAGE_MARGIN # switching authors has the effect of adding another c.BETWEEN_MESSAGES_MARGIN
            name_plus_timestamp_width = name_font.getsize(message.author.display_name)[0] + timestamp_font.getsize(get_time_text(message, now))[0]
        else:
            name_plus_timestamp_width = 0 # no need to calculate this again if we adjusted for it in this user's first message

        new_images = [get_image(image) for image in (message.attachments + message.embeds)]
        images[message.id] = new_images
        image_sizes = [image.size for image in new_images if image is not None]
        if message.clean_content is None:
            content_width = max([image_size[0] for image_size in image_sizes])
        elif len(image_sizes) == 0:
            content_width = content_font.getsize(message.clean_content)[0]
        else:
            content_width = max(content_font.getsize(message.clean_content)[0], max([image_size[0] for image_size in image_sizes]))
        message_width = max(name_plus_timestamp_width, content_width)
        if message_width > image_size[0]:
            if message_width > c.MAX_CONTENT_WIDTH:
                image_size[0] = c.MAX_CONTENT_WIDTH
            else:
                image_size[0] = message_width

        if message.clean_content is not None and len(message.clean_content) > 0:
            text_lines = len(wrap_text(message.clean_content, content_font, c.MAX_CONTENT_WIDTH))
            image_size[1] += text_lines * (c.MESSAGE_SIZE + c.BETWEEN_LINES_MARGIN)
        for one_image_size in image_sizes:
            image_size[1] += one_image_size[1]
        image_size[1] += c.BETWEEN_MESSAGES_MARGIN

        last_message = message

    image_size[0] += c.DEFAULT_LEFT_MARGIN + c.PFP_DIAMETER + c.PFP_TO_TEXT_MARGIN + c.DEFAULT_RIGHT_MARGIN # set this afterwards so we can do image_size[0] > c.MAX_CONTENT_WIDTH comparisons earlier
    image_size[1] += 2 * c.DEFAULT_V_MARGIN # add both a top and bottom margin
    return (image_size[0], image_size[1]), images, {"name": name_font, "timestamp": timestamp_font, "content": content_font}


def draw_quote(messages, image_size, images, fonts, store_avatar):
    background = Image.new("RGBA", image_size, c.BACKGROUND_COLOR)
    background_draw = ImageDraw.Draw(background)

    now = c.TIMEZONE.localize(dt.datetime.now()) # used for timestamping messages relative to when they're quoted
    last_message = None
    last_user_to_talk = None
    vertical_offset = c.BEGINNING_TOP_OFFSET - c.BETWEEN_AUTHORS_MARGIN # when we set the first last_user_to_talk, this will make the initial vertical offset = c.BEGINNING_TOP_OFFSET

    for message in messages:
        if message.author != last_user_to_talk or (message.created_at - last_message.created_at).total_seconds() > c.SECONDS_FOR_SEPERATED_MESSAGES:
            last_user_to_talk = message.author
            vertical_offset += c.BETWEEN_AUTHORS_MARGIN

            avatar_img = get_avatar_img(message.author, store_avatar)
            if avatar_img is not None: # sometimes we won't get the avatar for some reason; this is fine
                background.paste(avatar_img, (c.DEFAULT_LEFT_MARGIN, vertical_offset), avatar_img)

            background_draw.text((c.DEFAULT_LEFT_MARGIN + c.PFP_DIAMETER + c.PFP_TO_TEXT_MARGIN, vertical_offset), message.author.display_name, c.AUTHOR_COLOR, fonts["name"])
            background_draw.text((c.DEFAULT_LEFT_MARGIN + c.PFP_DIAMETER + c.PFP_TO_TEXT_MARGIN + fonts["name"].getsize(message.author.display_name)[0] + c.NAME_TO_TIMESTAMP_MARGIN, vertical_offset + c.TIMESTAMP_TOP_OFFSET), get_time_text(message, now), c.TIMESTAMP_COLOR, fonts["timestamp"])
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


def get_time_text(message, now):
    message_datetime = pytz.utc.localize(message.created_at).astimezone(c.TIMEZONE)
    datestring = ""
    day_offset = int((now - message_datetime).total_seconds() / 86400) # int division with discarding, so 1.1 days => yesterday, 0.9 days => today
    if day_offset >= 7:
        return message_datetime.strftime("%m/%d/%Y")
    if now.weekday() == message_datetime.weekday():
        if day_offset > 1:
            datestring += "Last " + c.WEEKDAY_NAMES[message.created_at.weekday()] + " at "
        else:
            datestring += "Today at "
    elif now.weekday() == (message_datetime.weekday() + 1) or (now.weekday() == 0 and message_datetime.weekday() == 6):
        datestring += "Yesterday at "
    else:
        datestring += "Last " + c.WEEKDAY_NAMES[message.created_at.weekday()] + " at "

    timestring = message_datetime.strftime("%I:%M %p")
    if timestring[0] == "0":
        timestring = timestring[1:] # 04:30 -> 4:30, since -I is broken on python 3.6
    return datestring + timestring


def circular_crop_avatar(avatar_img):
    circle_mask = Image.open(c.PFP_MASK_PATH).convert("RGBA")
    if avatar_img.size != circle_mask.size:
        avatar_img = avatar_img.resize(circle_mask.size, Image.ANTIALIAS)

    cropped_avatar = ImageChops.multiply(circle_mask, avatar_img) # can't use standard .putalpha masks because it makes the visible parts of transparent avatars non-transparent
    return cropped_avatar
