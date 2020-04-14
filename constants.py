import pytz
from default_modules.quotes import quote_module
from default_modules.reminders import reminders_module, start_remind_loop
from default_modules.roles import roles_module
from default_modules.statuses import status_loop

# main.py
DIRECTORIES = [
    "databases",
    "logs",
    "quotes/servers",
    "quotes/resources/avatars"
]

DEFAULT_MODULES = [
    quote_module,
    reminders_module,
    roles_module
]

DEFAULT_BACKGROUND_LOOPS = [
    start_remind_loop,
    status_loop
]

# akrasia.py
COMMAND_PREFIX = "!"
DATABASE_DIR = "databases"
DEFAULT_RETURN_MESSAGE = None
LOG_DATETIME_FORMAT = "%Y/%M/%d %H:%M:%S"
LOGS_DIR = "logs"
MAIN_DATABASE_NAME = "main.db"
MAX_REMINDER_FAILURES = 8
REMINDER_FAILURE_DELAY_TIME = {1: 10, 2: 60, 3: 60, 4: 60, 5: 3600, 6: 3600, 7: 3600}
REMINDER_LOOP_TIME_INCREMENT = 1
PREFIX_LENGTH = 1
TEXT_HOOKS = ["akrasia,"]
HOME_SERVER_ID = None # initialized by Akrasia.run()
AUTHOR_ID = None # initialized by Akrasia.run()
MAX_ALIASES_PER_SERVER = 5000
MAX_REMINDERS_PER_USER = 100
TRUNCATED_MESSAGE_LENGTH = 200
MAX_CHARS_PER_MESSAGE = 2000
SEND_CYCLE_WAIT_TIME = 0.5
AMBIGUOUS_ERROR = -1
QUOTES_COOLDOWN = 2
AVATAR_TEST_COOLDOWN = 5

MAGIC_8_BALL_RESPONSES = [
    "Without a doubt.",
    "As I see it, yes.",
    "Most likely.",
    "Outlook good.",
    "Signs point to yes.",
    "Reply hazy, try again.",
    "Ask again later.",
    "Better not tell you now.",
    "Cannot predict now.",
    "Concentrate and ask again.",
    "Don't count on it.",
    "My reply is no.",
    "My sources say no.",
    "Outlook not so good.",
    "Very doubtful."
]

CHANGE_STATUS_TIMER = 300

DEFAULT_HELP_DICT = {
			    "help": "honestly? i have no fuckin idea",
                            "echo": "**echo** *[message]*\n"
                            "*echo [channel] [message]*\n"
                            "*Permissions required: bot instance owner*\n"
                            "    Sends the given message to the given channel, or the current channel if no channel is given.\n"
                            "    `!echo uncle bill gave me his water bill for my third birthday`\n"
                            "    `!echo #general :crab: SHE TOOK THE KIDS :crab:\n",
                            "addalias": "**addalias** *[old command] [new keyword]*\n"
                            "*Permissions required: administrator*\n"
                            "    Creates a new command that executes old command (optionally with arguments).\n"
                            "    `!addalias echo say` => `!say They speak English in what?`\n"
                            "    `!addalias \"echo AAAAAAAAAAUGH\" SCREAM` => `!SCREAM`\n",
                            "deletealias": "**deletealias** *[alias]*\n"
                            "*Permissions required: administrator*\n"
                            "    Deletes an existing alias.\n"
                            "    `!deletealias SCREAM`\n",
                            "aliases": "**aliases**\n"
                            "*Permissions required: administrator*\n"
                            "    Lists all aliases on the current server. Be careful about running this if you've got a billion aliases.\n"
                            "    `!aliases`\n"
}
# logging.py
LOG_SLEEP_TIME = {"audit": 1, "log": 0.5}

# quotes.py
BEGINNING_TOP_OFFSET = 8 # personal choice
DEFAULT_V_MARGIN = 8 # 2 for the actual margin, 3 for the 3 pixels of space above the text, 3 for the 3 pixels of space below the previous text
DEFAULT_LEFT_MARGIN = 16
DEFAULT_RIGHT_MARGIN = 30 # personal choice
PFP_TO_TEXT_MARGIN = 16
PFP_DIAMETER = 40
NAME_TO_TIMESTAMP_MARGIN = 8
NAME_TO_MESSAGE_MARGIN = 6
BETWEEN_LINES_MARGIN = 6 # used to be 4
BETWEEN_MESSAGES_MARGIN = 4 # used to be 6
BETWEEN_AUTHORS_MARGIN = 16 # so the total space between the text from two authors is 16 + 10 + 4 = 30 px
AUTHOR_SIZE = 16
TIMESTAMP_SIZE = 12
MESSAGE_SIZE = 16
AUTHOR_COLOR = (255, 255, 255)
TIMESTAMP_COLOR = (114, 118, 125)
MESSAGE_COLOR = (220, 221, 222)
BACKGROUND_COLOR = (54, 57, 63)
QUOTES_DIR = "quotes/servers"
PFP_MASK_PATH = "quotes/resources/pfp_mask.png"
PFPS_FOLDER_PATH = "quotes/resources/avatars"
DISCORD_BOLD_FONT = "quotes/resources/Whitney-Semibold.ttf"
DISCORD_NORMAL_FONT = "quotes/resources/Whitney-Medium.ttf"
WEEKDAY_NAMES = {0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday", 4: "Friday", 5: "Saturday", 6: "Sunday"}
TIMESTAMP_TOP_OFFSET = 5
IMAGE_WIDTH = 700
MAX_EMBED_DIMENSIONS = (400, 300)
MESSAGE_TO_EMBED_SEPERATION = 11
SUPPORTED_IMAGE_FILETYPES = ["png", "jpg", "jpeg"] # gif?
MAX_EMBED_FILESIZE = 50 * 10**6 # 50 Mb
MAX_AVATAR_FILESIZE = 5 * 10**6 # 5 Mb
SECONDS_FOR_SEPERATED_MESSAGES = 7 * 60 # 7 minutes, as best as I can tell
MAX_QUOTES_PER_SERVER = 500
MAX_REVERSE_SEARCH_MESSAGES = 250
TIMEZONE = pytz.timezone("US/Eastern")
TEXT_TO_IMAGE_MARGIN = 4
AVATAR_TEST_MESSAGES = [
    "I have come here to chew bubblegum and kick ass.\nAnd I'm all out of bubblegum.",
    "I have come here to chew bubblegum and kick ass.\nAnd I'm all out of ass.",
    "Leverage agile frameworks to provide a robust synopsis for high level overviews. Iterative approaches to corporate strategy foster collaborative thinking to further the overall value proposition. Organically grow the holistic world view of disruptive innovation via workplace diversity and empowerment.",
    "Does he look like a bitch?",
    "i spent five minutes on google image search and all i got was this shitty avatar",
    "Yeah, twenty kilos. I'll pay in unmarked bills."
]

MAX_CONTENT_WIDTH = IMAGE_WIDTH - DEFAULT_LEFT_MARGIN - PFP_DIAMETER - PFP_TO_TEXT_MARGIN - DEFAULT_RIGHT_MARGIN # personal choice
