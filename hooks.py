from constants import MAGIC_8_BALL_RESPONSES
from random import choice

async def magic_eight_ball(_, __, ___):
    return choice(MAGIC_8_BALL_RESPONSES)

default_hooks = {
    "akrasia,": magic_eight_ball
}
