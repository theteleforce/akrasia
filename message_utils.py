import constants as c
import pytz

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


def get_time_text(datetime, now):
    offset_aware_now = c.TIMEZONE.localize(now)
    message_datetime = pytz.utc.localize(datetime).astimezone(c.TIMEZONE)
    datestring = ""
    day_offset = int((offset_aware_now - message_datetime).total_seconds() / 86400) # int division with discarding, so 1.1 days => yesterday, 0.9 days => today
    if day_offset >= 7:
        return message_datetime.strftime("%m/%d/%Y")
    if offset_aware_now.weekday() == message_datetime.weekday():
        if day_offset > 1:
            datestring += "Last " + c.WEEKDAY_NAMES[datetime.weekday()] + " at "
        else:
            datestring += "Today at "
    elif offset_aware_now.weekday() == (message_datetime.weekday() + 1) or (offset_aware_now.weekday() == 0 and message_datetime.weekday() == 6):
        datestring += "Yesterday at "
    else:
        datestring += "Last " + c.WEEKDAY_NAMES[datetime.weekday()] + " at "

    timestring = message_datetime.strftime("%I:%M %p")
    if timestring[0] == "0":
        timestring = timestring[1:] # 04:30 -> 4:30, since -I is broken on python 3.6
    return datestring + timestring
