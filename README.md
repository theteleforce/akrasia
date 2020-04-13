# Akrasia
Akrasia is a framework for writing and self-hosting Discord bots in Python. It is based on [discord.py](https://github.com/Rapptz/discord.py), and uses the same underlying classes, but implements [command aliases](#aliases), audit logging, database integration via SQLAlchemy, and easily adding groups of custom commands ("modules"). It comes with pre-installed modules for [quotes](#quotes), [role management](#role-management), and [reminders](#reminders).


The bot is designed with self-hosting in mind, and includes simple tools for adding your own commands and interaction with a database (either in memory, on disk, or remote). These short guides can walk you through setting up your own instance and adding custom commands:

  * Getting started
  * Adding commands

---
A short atlas of pre-installed commands is below. You can find out more by running `!help [command-name]`.
### Aliases  
Allows admins to add commands that redirect to existing commands, optionally with arguments.  
![#relateable #me #ilongfordeath](https://i.imgur.com/UbjA9WH.png)

__Commands__:
  * `!addalias [old command] [new alias]` to add an alias
  * `!deletealias [alias]` to delete an alias
  * `!aliases` to list all aliases
 
### Quotes
Stores a recreation of specified messages as a quote.  
![if you're reading this he's behind you](https://i.imgur.com/60o20Bf.png)

__Commands__:  
  * `!addquote` to add quotes  
  * `!deletequote` to delete quotes  
  * `!quote [search term]` to show a random quote with a given term or user  
  * `!quotes [search term]` to show all quotes with a given term or user  

### Reminders
Tell the bot to remind you of something after a given time period, or on a given day.  
![he's treated very well, don't worry](https://i.imgur.com/AV241C2.png)

__Commands__:  
  * `!remindme [time until reminder] [message]` to set a reminder that fires in 5 seconds, 10 minutes, etc.  
  * `!reminders` to list all your reminders in PM  
  * `!deletereminder [identifier]` to delete one of your reminders by text or ID  
   
### Role management
Allows admins to add or delete roles, and all users to join or leave them.  
![we are ever vigilant](https://i.imgur.com/Y9sDTwl.png)

__Commands__:
  * `!addrole [role name]` to make a role !joinable (adds it to the server if it doesn't exist)  
  * `!deleterole [role name]` to delete a role from the server  
  * `!unlistrole [role name]` to make a role un-!joinable again without deleting it  
  * `!join [role name]` to join a !joinable role  
  * `!leave [role name]` to leave any role  
  
### Utilities
`!help` and `!echo`.

__Commands__:
  * `!help` will list all commands on the bot
  * `!help [command name]` will display specific instructions for the command
  * `!echo [channel] [message]` will echo a message to a channel (can only be run by bot owner at the moment)
