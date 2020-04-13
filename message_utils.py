import constants as c

from asyncio import sleep

async def send_lines(recipient, lines):
    send_string = ""
    for line in lines:
        if len(line) > c.TRUNCATED_MESSAGE_LENGTH:
            new_line = line[:c.TRUNCATED_MESSAGE_LENGTH] + "[truncated]"
        else:
            new_line = line

        if len(send_string) + len(new_line) > c.MAX_CHARS_PER_MESSAGE:
            await recipient.send(send_string)
            send_string = new_line + "\n"
            await sleep(c.SEND_CYCLE_WAIT_TIME)
        else:
            send_string += new_line + "\n"
    await recipient.send(send_string)
