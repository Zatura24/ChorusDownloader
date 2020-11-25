import discord
import discord.ext.commands
import patoolib
import os
import requests
import logging
import tempfile
from asyncio import TimeoutError
from cgi import parse_header
from configparser import ConfigParser
from dotenv import load_dotenv

logging.basicConfig(filename='discord.log', level=logging.INFO)

config = ConfigParser()
config.read('config.ini')

downloaded_songs_list = []

REQUEST_HEADER = {'User-Agent': 'Mozilla/5.0'}
API_URL = config['BOT']['apiUrl']

bot = discord.ext.commands.Bot(
    command_prefix=config['BOT']['discordCommandPrefix'])

if not os.path.exists(config['BOT']['downloadPath']):
    os.makedirs(config['BOT']['downloadPath'])
if not os.path.isfile(config['BOT']['downloadedSongsCacheFile']):
    os.mknod(config['BOT']['downloadedSongsCacheFile'])
else:
    with open(config['BOT']['downloadedSongsCacheFile'], 'r') as filehandle:
        downloaded_songs_list = [int(line.rstrip('\n')) for line in filehandle]


@bot.event
async def on_command_error(ctx: discord.ext.commands.Context, error):
    logging.exception(error)
    await ctx.send("Oops! It looks like my human isn't a good programmer afterall... 🦄")


@bot.command(name='ping')
async def pong(ctx):
    await ctx.send('pong')


@bot.command(name='api', help='Gets or sets the api')
@discord.ext.commands.has_role('admin')
async def get_or_set_api(ctx: discord.ext.commands.Context, api_url: str = None):
    global API_URL

    if not API_URL and not api_url:
        return await ctx.send_help('api')

    if api_url:
        API_URL = api_url + '/' if not api_url.endswith('/') else api_url
        with open('config.ini', 'w') as configfile:
            config['BOT']['apiUrl'] = API_URL
            config.write(configfile)
        await ctx.send('Api url set to: %s' % API_URL)
    else:
        await ctx.send('Api url is: %s' % API_URL)


@bot.command(name='search', help='Make a search request using a string with an optional type. After that select a song by typing it\'s numerical value')
async def search_and_download(ctx: discord.ext.commands.Context, search_string: str, query_type: str = None):
    if not API_URL:
        return await ctx.send('```First, add an api url with: {0}api <url>```'.format(config['DISCORD']['discordCommandPrefix']))

    # Make the search request and present the user with the response
    apiData = get_api_data_json(API_URL, search_string, query_type)
    apiResultChoice = generate_choise_result(apiData)
    apiResponse = discord.Embed(
        title=ctx.message.author.name,
        colour=discord.Colour.blue(),
        description='\n'.join(apiResultChoice)
    )
    apiResponse.set_footer(text='Type a number to download it')
    choisesMessage = await ctx.send(embed=apiResponse, delete_after=config['BOT'].getfloat('defaultTimeout'))

    # Handeling the user response
    def is_valid_respone(message):
        return ctx.message.author.name == message.author.name and message.content.isdigit() and 0 < int(message.content) <= len(apiData['songs'])

    try:
        responseMessage = await bot.wait_for('message', check=is_valid_respone, timeout=config['BOT'].getfloat('defaultTimeout'))
        songToDownload = apiData['songs'][int(responseMessage.content) - 1]

        async def send_download_message(songToDownload: dict, message: str):
            return await ctx.send(message + '{0} - {1}'.format(songToDownload['name'], songToDownload['artist']))

        if songToDownload['id'] in downloaded_songs_list:
            return await send_download_message(songToDownload, '✅ Already downloaded: ')
        else:
            await choisesMessage.delete()
            downloadingMessage = await send_download_message(songToDownload, '⌛ Downloading: ')
            if download_song(songToDownload):
                await send_download_message(songToDownload, '✅ Downloaded: ')
            else:
                await send_download_message(songToDownload, '❌ Error downloading: ')
            await downloadingMessage.delete()
    except TimeoutError:
        pass  # ignoring because the user did not respond. Nothing went wrong


def get_api_data_json(apiUrl: str, search_string: str, query_type: str = None):
    url = apiUrl + 'search?query={0}%3D%22{1}%22'.format(
        query_type, search_string) if query_type else apiUrl + 'search?query={0}'.format(search_string)
    return requests.get(url, headers=REQUEST_HEADER).json()


def generate_choise_result(apiData: dict):
    def tierGuitar(song): return ' | '+('⭐' * int(song['tier_guitar']))
    return [
        '`{0}` {1} - {2}{3}'.format(i, song['name'],
                                    song['artist'], tierGuitar(song) if song['tier_guitar'] else '')
        for i, song in enumerate(apiData['songs'], start=1)
    ]


def download_song(songToDownload: dict):
    global downloaded_songs_list

    if 'directLinks' in songToDownload:
        if 'archive' in songToDownload['directLinks']:
            with tempfile.TemporaryDirectory() as temporaryDirectory:
                downloadedFile = download_song_to_path(
                    songToDownload['directLinks']['archive'], temporaryDirectory)
                extrach_archive(downloadedFile, temporaryDirectory,
                                config['BOT']['downloadPath'])
        else:
            fullDownloadPath = os.path.join(
                config['BOT']['downloadPath'], songToDownload['name'])
            os.makedirs(fullDownloadPath)
            for directLink in songToDownload['directLinks']:
                download_song_to_path(
                    songToDownload['directLinks'][directLink], fullDownloadPath)

        downloaded_songs_list = cache_downloaded_song(songToDownload['id'],
                                                      downloaded_songs_list,
                                                      config['BOT']['downloadedSongsCacheFile'])
        return True
    return False


def download_song_to_path(downloadLink: str, downloadPath: str):
    with requests.get(downloadLink, headers=REQUEST_HEADER, stream=True) as response:
        # Bypass Google drive virus scanning warning
        downloadWarning = check_for_download_warning(response)
        if downloadWarning:
            response = requests.get(downloadLink+'&confirm='+response.cookies[downloadWarning],
                                    headers=REQUEST_HEADER,
                                    cookies=response.cookies,
                                    stream=True)
        response.raise_for_status()

        filename = get_filename_from_content_disposition(
            response.headers.get('Content-Disposition'))
        downloadPath = os.path.join(downloadPath, filename)

        with open(downloadPath, 'wb') as filehandle:
            for chunk in response.iter_content(chunk_size=config['BOT'].getint('chunkSize')):
                filehandle.write(chunk)

    return filename


def get_filename_from_content_disposition(cd: str):
    _, data = parse_header(cd)
    return data['filename'] if 'filename' in data else None


def extrach_archive(filename: str, tempFolder: str, download_folder: str):
    tempFile = os.path.join(tempFolder, filename)
    patoolib.extract_archive(tempFile, verbosity=-1,
                             outdir=download_folder+'/', interactive=False)


def cache_downloaded_song(id: int, songList: list, songListFile: str):
    with open(songListFile, 'w') as filehandle:
        filehandle.writelines([str(songId) + "\n" for songId in songList])

    return songList + [id]


def check_for_download_warning(response: requests.Response):
    return next((link for link in response.cookies.get_dict() if link.startswith('download_warning')), None)


bot.run(os.getenv('DISCORD_TOKEN'))
