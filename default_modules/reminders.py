import constants as c
import sqlalchemy as db

from asyncio import gather, sleep
from database_utils import Reminder
from datetime import datetime as dt
from datetime import timedelta as td
from dateutil.relativedelta import relativedelta
from message_utils import send_lines
from default_modules.quotes import get_time_text

# Asynchronous (Discord) stuff
async def remind_me(client, message, command_args, session):
    if message.author.bot:
        return "Robots can't receive reminders!"

    if len(command_args) < 2:
        return "Must include a time (8 seconds, 16 hours, 04/17/2020, etc) and a message!"

    try:
        remind_at, n_time_arguments = parse_time(command_args)
    except Exception as e:
        client.bot_log.warning("Failed to parse time in !remindme for user {} (id: {}); error was: {}".format(message.author.name, message.author.id, e))
        return "{}".format(e)

    remind_message = " ".join(command_args[n_time_arguments:])
    if remind_message == "":
        client.bot_log.warning("!remind_me called by user {} (id: {}) without a message".format(message.author.name, message.author.id))
        return "No message found!"

    return_message = c.DEFAULT_RETURN_MESSAGE
    try:
        reminders_for_user = session.query(Reminder).filter(Reminder.user_id == message.author.id).all()
        if len(reminders_for_user) > c.MAX_REMINDERS_PER_USER:
            client.bot_log.error("Couldn't set reminder for user {} (id: {}) to fire on {}; user exceeded max reminders\nreminder was:{}".format(message.author.name, message.author.id, remind_at, remind_message))
            return "You're at the maximum number of reminders ({}). Hopefully they aren't too long away!".format(
                c.MAX_REMINDERS_PER_USER)
        session.add(Reminder(message=remind_message, send_at=remind_at, user_id=message.author.id, failures=0))
        if n_time_arguments == 1:
            return_message = "Reminder set for {}!".format(command_args[0])
        else:
            return_message = "Reminder set for {} from now!".format(" ".join(command_args[:2]))
        client.bot_log.info("Set reminder for user {} (id: {}) to fire on {}; text: {}".format(message.author.name, message.author.id, remind_at, remind_message))
    except Exception as e:
        client.bot_log.error("Couldn't set reminder for user {} (id: {}) to fire on {}; error was {}\nreminder was:{}".format(message.author.name, message.author.id, remind_at, e, remind_message))
        raise Exception()
    finally:
        return return_message


async def delete_reminder(client, message, command_args, session):
    if len(command_args) == 0:
        return "Which reminder? (you can specify by ID or substring search)"

    if len(command_args) == 1:  # if there's one arg, try to delete it by ID first
        try:
            reminder_id = int(command_args[0])

            reminder = session.query(Reminder).filter(db.and_(Reminder.user_id == message.author.id, Reminder.id == reminder_id)).first()
            if reminder is not None:
                session.delete(reminder)
                return_string = "Reminder with ID {} deleted!\nText was: ".format(reminder_id)
                if len(reminder.message) > c.TRUNCATED_MESSAGE_LENGTH:
                    return_string += reminder.message[:c.TRUNCATED_MESSAGE_LENGTH] + "...[truncated]"
                else:
                    return_string += reminder.message
                return return_string
        except:
            client.bot_log.info("Failed to delete reminder for user {} (id: {}) with given ID {}; trying substring search...".format(message.author.name, message.author.id, command_args[0]))

    search_string = " ".join(command_args)
    matching_reminders = session.query(Reminder).filter(db.and_(Reminder.user_id == message.author.id, Reminder.message.ilike(search_string))).all()
    if len(matching_reminders) == 0:
        client.bot_log.info("No matching reminders found for user {} (id: {}) for search term {}".format(message.author.name, message.author.id, search_string))
        return "No reminders matching that ID or substring found! Try listing your reminders with !reminders and removing by ID."
    elif len(matching_reminders) > 1:
        client.bot_log.info("Couldn't remove reminder for user {} (id: {}); search term {} was ambiguous".format(message.author.name, message.author.id, search_string))
        message.author.send("Ambiguous search term (found {} matching reminders:)\n".format(len(matching_reminders)))
        await __list_reminders(message.author, matching_reminders)
    else:
        session.delete(matching_reminders[0])
        client.bot_log.info("Removed reminder for user {} (id: {})".format(message.author.name, message.author.id))
        await message.author.send("Reminder deleted!")


async def reminders(client, message, _, session):
    reminders_for_user = session.query(Reminder).filter(Reminder.user_id == message.author.id).all()
    if len(reminders_for_user) == 0 or reminders_for_user is None:
        return "No reminders found!"

    await message.author.send("{} reminders found:\n".format(len(reminders_for_user)))
    client.bot_log.info("Listing reminders to user {} (id: {})".format(message.author.name, message.author.id))
    await __list_reminders(message.author, reminders_for_user)


async def __list_reminders(user, reminder_list):
    reminder_strings = ["[ID: {}] [{}] {}".format(reminder.id, reminder.send_at.strftime("%m/%d/%Y %I:%M %p"), reminder.message) for reminder in reminder_list]
    await send_lines(user, reminder_strings)


async def start_remind_loop(client):
    session = client.db_session_builder()  # might need to initiate a new session every once in a while if old ones time out, but i have no evidence that they do
    while True:
        loop_start_time = dt.now()

        try:
            reminders_to_fire = session.query(Reminder).filter(Reminder.send_at <= loop_start_time).all()
        except Exception as e:
            client.bot_log.error("Couldn't check for reminders in database; error was {}".format(e))
            await async_sleep_n_seconds(c.REMINDER_LOOP_TIME_INCREMENT, loop_start_time)
            continue
        if len(reminders_to_fire) > 0:
            reminder_tasks = [remind_user(client, reminder) for reminder in reminders_to_fire]
            results = await gather(*reminder_tasks)

            reminders_to_remove = []
            reminders_to_delay = []
            for result in results:
                session.add(result[0])  # save whatever changes we'll be making either weay
                if result[1]:
                    reminders_to_remove.append(result[0])
                else:
                    reminders_to_delay.append(result[0])

            if len(reminders_to_remove):
                try:
                    print()
                    session.query(Reminder).filter(Reminder.id.in_([reminder.id for reminder in reminders_to_remove])).delete(synchronize_session=False)
                except Exception as e:
                    client.bot_log.error("Failed to delete sent reminders from the database; error was: {}".format(e))
            if len(reminders_to_delay):
                for reminder in reminders_to_delay:
                    reminder.failures += 1
                    if reminder.failures == c.MAX_REMINDER_FAILURES:
                        client.bot_log.warning("Reminder to user with ID {} failed too main times; deleting it\ntext was: {}".format(reminder.user_id, reminder.message))
                        try:
                            session.query(Reminder).filter(Reminder.id == reminder.id).delete(
                                synchronize_session="evaluate")
                        except Exception as e:
                            client.bot_log.error("Failed to delete failed reminders from the database; error was: {}".format(e))
                    else:
                        reminder.send_at += td(seconds=c.REMINDER_FAILURE_DELAY_TIME[reminder.failures])
                        client.bot_log.warning("Reminder to user with ID {} failed (failure count: {}); text was {}".format(reminder.user_id, reminder.failures, reminder.message))

            try:
                session.commit()
            except Exception as e:
                client.bot_log.error("Failed to commit reminder session to database; trying to restart session (error was: {})".format(e))
                session.close()
                session = client.db_session_builder()
        await async_sleep_n_seconds(c.REMINDER_LOOP_TIME_INCREMENT, loop_start_time)


async def remind_user(client, reminder):
    client.bot_log.info("Attempting to remind user with ID {} with message: {}".format(reminder.user_id, reminder.message))
    try:
        reminder_text = get_time_text(reminder.send_at, dt.now())
        await client.get_user(reminder.user_id).send("{}\n(in response to your reminder set {}{})".format(reminder.message, reminder_text[0:1].lower(), reminder_text[1:]))
        client.bot_log.info("Successfully reminded user with ID {} with message: {}".format(reminder.user_id, reminder.message))
        return reminder, True
    except Exception as e:
        client.bot_log.error("Failed to remind user with ID {}; error was {}\nmessage was: {}".format(reminder.user_id, e, reminder.message))
        return reminder, False


# Synchronous (client-side) stuff
def parse_time(message_args):
    now = dt.now() # since resolution can't be smaller than seconds, no risk to fetching this before some simple operations
    datetime_parts = message_args[0].split("/") # safe because we check for len == 0 before calling this
    if len(datetime_parts) > 1:
        remind_month = int(datetime_parts[0])
        remind_day = int(datetime_parts[1])
        if len(datetime_parts) > 2: # silently ignore everything after the third slash
            remind_year = int(datetime_parts[2])
        else:
            remind_year = now.year
        remind_at = dt(remind_year, remind_month, remind_day)
        if remind_at <= now:
            raise ValueError("Sorry, my time machine's still on the fritz.")
        return remind_at, 1
    else:
        if len(message_args) < 2:
            raise ValueError("Invalid time (allowed formats: seconds, minutes, hours, days, weeks, months, years, or dates in format mm/dd/yyyy")
        else:
            time_unit = message_args[1].lower()
            time_quantity = int(message_args[0])
            if time_quantity < 1:
                raise ValueError("Sorry, my time machine's still on the fritz.")
            if time_unit in c.SECONDS_ALIAS:
                return now + relativedelta(seconds=int(message_args[0])), 2
            elif time_unit in c.MINUTES_ALIAS:
                return now + relativedelta(minutes=int(message_args[0])), 2
            elif time_unit in c.HOURS_ALIAS:
                return now + relativedelta(hours=int(message_args[0])), 2
            elif time_unit in c.DAYS_ALIAS:
                return now + relativedelta(days=int(message_args[0])), 2
            elif time_unit in c.WEEKS_ALIAS:
                return now + relativedelta(weeks=int(message_args[0])), 2
            elif time_unit in c.MONTHS_ALIAS:
                return now + relativedelta(months=int(message_args[0])), 2
            elif time_unit in c.YEARS_ALIAS:
                return now + relativedelta(years=int(message_args[0])), 2
            raise ValueError("Invalid time type passed: {}".format(time_unit))


async def async_sleep_n_seconds(n, loop_start_time):
    time_elapsed = dt.now() - loop_start_time
    if time_elapsed.total_seconds() < n: # if it's been n seconds already, no need to sleep at all
        await sleep(n - time_elapsed.total_seconds() - (time_elapsed.microseconds/10**6))

reminders_module = {
    "remindme": (remind_me, "**remindme** [timespan] [message]\n"
                            "*remindme [date] [message]*\n"
                            "*Permissions needed: none:*\n"
                            "    Sends the user a DM with a given message on the given date, or after the given time has elapsed.\n"
                            "    `!remindme 30 minutes way to spend 30 minutes` will send the user the message after 30 minutes\n"
                            "    `!remindme 5/01/2020 iron the gimp` will send the user the message at midnight on October 30th, 2020"),
    "reminders": (reminders, "**reminders**\n"
                             "*Permissions needed: none*\n"
                             "    DM's the user a list of their current reminders and their IDs\n"
                             "    `!reminders` will DM you a list of your reminders"),
    "deletereminder": (delete_reminder, "**deletereminder** *[reminder ID]*\n"
                                        "*deletereminder [text in reminder]*\n"
                                        "*Permissions needed: none*\n"
                                        "    Removes one of your reminders specified by ID, or by having the provided text string in it.\n"
                                        "    (reminder IDs can be checked using !reminders)"
                                        "    `!deletereminder 2` will delete your reminder with ID 2."
                                        "    `!deletereminder iron the gimp` will delete the first of your reminders with \"iron the gimp\" in it.")
}
