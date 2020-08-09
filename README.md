# 🎶 Chorus Downloader 🎶
Chorus Downloader is a discord bot for downloading songs of Chorus like repositories.

# Install
First create a docker image:
```bash
docker build -t chorusdownloader .
```

Secondly run the docker image:
```bash
docker run -d --name ChorusDownloader chorusdownloader
```

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