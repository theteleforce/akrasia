# Setting up your own Akrasia instance

This tutorial will walk you through setting up Akrasia to the point where it can run on a server. Getting to this point should take no
longer than ~5 minutes.

There are four major steps:
  1. [Creating a Discord application](#creating-a-discord-application) that the bot will run on. Note that, since this is *your* application, you can name it whatever you want, and give it its own avatar.
  2. [Downloading this repository](#downloading-the-code) to the device you want to run the bot on.
  3. [Tying the two together](#running-the-bot-for-the-first-time), giving life to your bot.
  4. [Adding the bot to a server.](#adding-the-bot-to-a-server)
  
If you're familiar enough with the Discord API or Github to do steps 1 and 2 on your own, feel free to skip to step 3. Otherwise, read on.

## Creating a Discord application

First, we'll register a bot with Discord. At the end of this step, you'll have made a bot account and acquired a token that you can give
your Akrasia instance to let it operate on that account.

  1) Go to https://discordapp.com/developers and sign in using your Discord account. 
  2) Click the `New Application` button in the top right. Give the bot a name (it can be anything you want!). Once you've done that, you should see something like this:
  ![nice try](https://i.imgur.com/5GHipmy.png)  
  Here you can set the icon and the username, if you want.
  3) We don't need any of the stuff on that screen. Instead, we're going to click into the `Bot` tab on the left, click `Add Bot`, and confirm that you really want to.
  4) Click `Copy` beneath the token (or just keep the page open; you'll need it later.) If you don't want anyone else to be able to add your bot, also make sure to uncheck `Public Bot` in the options below the token.
  ![i'm in the mainframe](https://i.imgur.com/qbwk5ae.png)
  5) We're done with the first step! Next up: downloading and setting up the code.
  
## Downloading the code

Once the bot account is set up, we'll need to install the code on whatever device you want to run the bot on. Note that *the bot will always be running in the background on this device.*
It's not CPU-intensive, but it is something to consider; if your internet goes out or you shut down the device, you'll have to restart the bot when that device reboots.

You'll need [Git](https://git-scm.com/book/en/v2/Getting-Started-Installing-Git) and [Python 3](https://realpython.com/installing-python/#windows) installed for this. If you're installign on Linux or Mac, you should have them already.

Once you have those, getting the code is very easy:

  1) Navigate via command line to the directory you want to run the bot in, then run `git clone https://github.com/CocoPommel/akrasia`, then `cd akrasia`.
  2) (OPTIONAL) If you want to run Python in a virtual environment:  
     * On Linux or Mac, run `python3 -m pip install --user virtualenv`, then `python3 -m venv env`, then `source env/bin/activate`.
     * On Windows, run `py -m pip install --user virtualenv`, then `py -m venv env`, then `.\env\Scripts\activate`.
  3) Run `pip install -r requirements.txt` to install the dependencies.
  
That's it! In theory, you would be able to run the bot now; however, we still need a few things from part 1.

## Running the bot for the first time
In the Git repository you downloaded, there's a file called `config.json`. Our last steps will consist of filling that file with useful information. Notably, your token, your user ID, and the ID of a home server.

  1) Paste the token from your Discord bot page *in the quotes* across from `"token":`. **Don't** ever push this file to GitHub after this point; anyone who gets ahold of your bot token will be able to control your bot.
  2) Paste your user ID (without quotes) across from `"author_id":`. This will be used to ping you if the bot runs into a backend error.    
  If you don't know how to get your ID, go to `Discord Settings > Appearance` and check `Enable Developer Mode`. This lets you get your user ID just by right-clicking on your avatar (as well as the ID of any server by right-clicking on its icon)  
  ![:crab: SHE TOOK THE KIDS :crab:](https://i.imgur.com/sv2FXlW.png)
  3) Finally, Akrasia requires a home server if you plan on using the `quotes` module (if you don't, just set this to 0). Create a new Discord server, copy the ID, and paste it across from `"home_server"`.

That's it! Now you can run the bot with `python3 main.py` on Mac or Linux, or `py main.py` on Windows.

## Adding the bot to a server
To finish setup, we'll add the bot to its home server.

  1) Go back to the Discord bot page from earlier. Switch to the `OAuth2` tab on the left. 
  2) Underneath Scopes, check the box for `Bot`. Under `Permissions`, for the default modules, you need at least the following permissions selected:  
  ![manage-roles-manage-channels-view-channels-send-messages-embed-links-attach-files-read-message-history](https://i.imgur.com/H1mQ8dT.png)
  3) Once you've selected the permissions, copy the generated link above (it should start with https://discordapp.com/api/oauth2)
  4) Open a new tab and paste this link. When asked to choose a server, pick the home server you created earlier from the dropdown.

Now all that's left is to test it:
![you did it](https://i.imgur.com/0OLnWzY.png)
 
 And that's it! Your instance of Akrasia should be good to go. You can add it to other servers using the same link as before, or take a
 deeper dive and implement your own commands at Intro to modding.
 
