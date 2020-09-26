# 🎶 Chorus Downloader 🎶
Chorus Downloader is a discord bot for downloading songs of Chorus like repositories.

This bot is based on the API created by Paturages: [Chorus](https://github.com/Paturages/chorus)


# Avaiable commands
Following is a list of available commands.

`$ping`
pong

`$api [url]`
Gets or Sets the api url.  
__Note__: requires 'admin' role

`$search <search_string> [query_type]`
Searches the api for a given 'search_string'. Optionaly a query_type can be supplied. These are currently the same as documented in Paturages API.  
__Note__: If more than one word is needed for the search, the search_string needs to be encapsulated in quotes

# Install
Make sure to first create a discord bot, and have it's token ready. A tutorial can be found here: [Creating a bot account](https://discordpy.readthedocs.io/en/latest/discord.html). Also make sure to create an Admin role inside your discord server, because this necessary for setting the url.

First create a docker image:
```bash
docker build -t chorusdownloader .
```

Secondly run the docker image:
```bash
docker run -d --name ChorusDownloader --env DISCORD_TOKEN=xxxx chorusdownloader
```

> Note: As a default there is no volume attached to the download folder. You must add one yourself with the `-v` parameter.

## Environment variables
The following environment variables can be set during the docker run command:
* Required
    * DISCORD_TOKEN
* Optional
    * DISCORD_COMMAND_PREFIX
    * CHORUS_API
    * CHORUS_DOWNLOAD_PATH
    * CHORUS_CACHE_EXPIRE_AFTER_SECONDS

To add these to the docker run command use `--env KEY=VALUE`