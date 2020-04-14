# Adding custom commands

In this tutorial, we'll add a simple command to Akrasia -- one that rolls dice. We'll also go over broader concepts, like how Akrasia treats modules.

## Adding a command function

We'll start off by creating a new folder named `custom_modules` in the same directory as `main.py`. This isn't strictly necessary, but helps to keep code organized.
Then, we'll create `dice.py` in that directory. Your directory should now look something like this:  

![peek behind the scenes](https://i.imgur.com/vHkkOXc.png)

Inside `dice.py`, we'll define a function called `roll`. This is the function that will actually be called when a user types `!roll`.
In Akrasia, such functions must look something like this:
```
async def roll(client, message, command_args, session):
    return "4"
```
Let's break this down into parts:
  * `async` is there because *all functions called directly by commands* must be asynchronous. Helper functions called by those functions can be synchronous, but good practice is to do operations that block for a while asynchronously if possible.
  * The four arguments must also be present in any function called directly by a command.
    * `client` holds the `discord.Client` object for your bot. This allows you to do things like update your status, get users by ID, and other Discord API things.
    * `message` has the `discord.Message` object that triggered this command. Most commonly used to get the `message.author`, `message.guild`, and `message.channel`.
    * `command_args` contains the arguments passed by the user; for example, `!roll a b c` gives `["a", "b", "c"], while `!roll "a b" c` gives ["a b", "c"]
    * `session` is the SQL session created for this request. It is automatically committed when your function returns and rolls back on error, so you don't need to worry about closing or handling every error.
  * The return message is what your bot will respond to the user with. Every command must return *something*, even if it's just confirmation that it run successfully, because otherwise one million (1,000,000) people will DM you asking why your bot is down.
  
In most commands, you won't use all of these arguments. That's no problem! Just remember, they have to *be* there, or the bot can't call your function.

Now your command exists. However, Akrasia doesn't *know* it exists. To fix this, we need to add it to a *module*.

## Adding a module

Modules are how Akrasia packages commands. You'll usually put multiple related commands (say, `!join` and `!leave`, or `!rip` and `!tear`) in the same module. Let's see how it works.

At the bottom of `dice.py`, add the following code:
```
dice_module = {
    "roll": (roll, "Rolls an RFC 1149.5-certified die")
}
```

Each key-value pair represents a command. They key is what the user will type to execute your command. The value is a two-part (function, help message) tuple.
Simply put, when a user types `!roll`, the bot will run `roll`, and when a user types `!help roll`, they'll be sent the help message.
Every function needs a help message, even if it's an empty string[1].

We're actually almost done. Open `main.py` and add an import for your module:
```
from custom_modules.dice import dice_module
```
Then add `dice_module` to the `custom_modules` array:
```
custom_modules = [dice_module]
```

And that should be it! Start up the bot and give it a whirl:

![*zelda item get sound*](https://i.imgur.com/nC3X4vf.png)

We did it! Now...

## Making a not shit command

Let's improve this command some. Specifically, let's make it so you can roll any number of any-sided dice (2d6, 5d4), in case you've got any huge nerds on your server.

The input would look something like this:  
`!roll 5d4` 
Meaning our code should look something like this (feel free to implement this yourself, if you want):
```
from random import randint

async def roll(client, message, command_args, session):
    num_die, num_sides = [int(n) for n in command_args[0].split("d")]
    
    total_roll = 0
    for _ in range(num_die):
      total_roll += randint(1, num_sides)
    
    return str(total_roll)
```

Implementing and running this, we can see it works as expected:  

![four AM btw](https://i.imgur.com/LoZEnjA.png)

But wait. What if a clueless new user comes in and does this?
![fuck you joe gonzalez](https://i.imgur.com/7yJ4HkR.png)

Or some incredible bastard does this?
![the hacker known as 4chan](https://i.imgur.com/jaUjPkH.png)

Clearly, we need to validate our input.

## Check your user input (or you'll get pinged a lot)
As a rule, everyone on the internet is the kind of person who parks in disabled parking spaces while driving a stolen SUV with a Holacaust denial spray-painted on it.
To counter this, you should be very sure to *check everything in command_args before you use it*.

Here, there's serveral possible errors:
  * No arguments were submitted (in this case, command_args[0] throws an exception)
  * There wasn't a `d` in the string, or more than one `d`, or a `d` was at the end...
  * One of the numbers wasn't actually a number (`!roll 2dsix`)
  * Extremely high numbers of rolls or sides

Here's an example that fixes all of them:
```
async def roll(client, message, command_args, session):
    try:
        num_die, num_sides = [int(n) for n in command_args[0].split("d")]
    except Exception as e:
        return "Couldn't parse that input. Try `!help roll`."
      
    if num_die > 100:
        return "Can't role more than 100 dice at once!"
    
    try:
        total_roll = 0
        for _ in range(num_die):
            total_roll += randint(1, num_sides)
    except OverflowError:
        return "those dice are practically spheres wtf"
    
    return str(total_roll)
```
There's no deeper lesson or meaning here. Just check your input.

## Logging and other arguments
Since Akrasia features built-in logging, it'd go amiss not to mention it here. This also gives us a chance to look at the `message` object some more, since it's probably the second most useful argument.

Logs are made via calls to the `client.bot_log`. They come in multiple levels: `client.bot_log.info()`, `client.bot_log.warning()`,
and `client.bot_log.error()`. Since all of these fairly self-explanatory, I'll just complete the example below.

```
async def roll(client, message, command_args, session):
    try:
        num_die, num_sides = [int(n) for n in command_args[0].split("d")]
    except Exception as e:
        client.bot_log.info("User {} (id: {}) called !roll with malformed args: {}".format(message.author.name, message.author.id, command_args))
        return "Couldn't parse that input. Try `!help roll`."
      
    if num_die > 100:
        client.bot_log.warning("User {} (id: {}) called !roll with too many dice.".format(message.author.name, message.author.id))
        return "Can't role more than 100 dice at once!"
    
    try:
        total_roll = 0
        for _ in range(num_die):
            total_roll += randint(1, num_sides)
    except OverflowError:
        return "those dice are practically spheres wtf"
    
    return str(total_roll)
```

## Conclusion

That's about it.[2] At some point I'll make a second tutorial about how to use the database, if demand is high enough. Until then, reading through the [SQLAlchemy docs](https://docs.sqlalchemy.org/en/13/) will have to do.

Happy modding!

[1] Don't make your help message an empty string.
[2] You may need some extra libraries, depending on what you want to do. The main one is PyNaCl, which you'll need if you want to implement any voice channel-related functions.
