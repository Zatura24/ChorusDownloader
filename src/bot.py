"""Bot"""
import os
import logging
import tempfile
from asyncio import TimeoutError
from cgi import parse_header
from configparser import ConfigParser
import discord
import discord.ext.commands
import patoolib
import requests

logging.basicConfig(filename='discord.log', level=logging.INFO)

config = ConfigParser()
config.read('config.ini')

REQUEST_HEADER = {'User-Agent': 'Mozilla/5.0'}
API_URL = config['BOT']['apiUrl']
DOWNLOADED_SONGS_LIST = []

bot = discord.ext.commands.Bot(
    command_prefix=config['BOT']['discordCommandPrefix'])

if not os.path.exists(config['BOT']['downloadPath']):
    os.makedirs(config['BOT']['downloadPath'])
if not os.path.isfile(config['BOT']['downloadedSongsCacheFile']):
    os.mknod(config['BOT']['downloadedSongsCacheFile'])
else:
    with open(config['BOT']['downloadedSongsCacheFile'], 'r') as filehandle:
        DOWNLOADED_SONGS_LIST = [int(line.rstrip('\n')) for line in filehandle]


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
    api_data = get_api_data_json(API_URL, search_string, query_type)
    api_result_choice = generate_choise_result(api_data)
    api_response = discord.Embed(
        title=ctx.message.author.name,
        colour=discord.Colour.blue(),
        description='\n'.join(api_result_choice)
    )
    api_response.set_footer(text='Type a number to download it')
    choises_message = await ctx.send(embed=api_response, delete_after=config['BOT'].getfloat('defaultTimeout'))

    # Handeling the user response
    def is_valid_respone(message):
        return ctx.message.author.name == message.author.name and message.content.isdigit() and 0 < int(message.content) <= len(api_data['songs'])

    try:
        response_messasge = await bot.wait_for('message', check=is_valid_respone, timeout=config['BOT'].getfloat('defaultTimeout'))
        song_to_download = api_data['songs'][int(
            response_messasge.content) - 1]
        await choises_message.delete()

        async def send_download_message(song_to_download: dict, message: str):
            return await ctx.send(message + '{0} - {1}'.format(song_to_download['name'], song_to_download['artist']))

        if song_to_download['id'] in DOWNLOADED_SONGS_LIST:
            return await send_download_message(song_to_download, '✅ Already downloaded: ')

        downloading_message = await send_download_message(song_to_download, '⌛ Downloading: ')
        if download_song(song_to_download):
            await send_download_message(song_to_download, '✅ Downloaded: ')
        else:
            await send_download_message(song_to_download, '❌ Error downloading: ')
        await downloading_message.delete()
    except TimeoutError:
        pass  # ignoring because the user did not respond. Nothing went wrong


def get_api_data_json(apiUrl: str, search_string: str, query_type: str = None):
    url = apiUrl + 'search?query={0}%3D%22{1}%22'.format(
        query_type, search_string) if query_type else apiUrl + 'search?query={0}'.format(search_string)
    return requests.get(url, headers=REQUEST_HEADER).json()


def generate_choise_result(apiData: dict):
    def tierGuitar(song):
        return ' | '+('⭐' * int(song['tier_guitar']))

    return [
        '`{0}` {1} - {2}{3}'.format(i, song['name'],
                                    song['artist'], tierGuitar(song) if song['tier_guitar'] else '')
        for i, song in enumerate(apiData['songs'], start=1)
    ]


def download_song(song_to_download: dict):
    global DOWNLOADED_SONGS_LIST

    if 'directLinks' in song_to_download:
        if 'archive' in song_to_download['directLinks']:
            with tempfile.TemporaryDirectory() as temporary_directory:
                downloaded_file = download_song_to_path(
                    song_to_download['directLinks']['archive'], temporary_directory)
                extrach_archive(downloaded_file, temporary_directory,
                                config['BOT']['downloadPath'])
        else:
            full_download_path = os.path.join(
                config['BOT']['downloadPath'], song_to_download['name'])
            os.makedirs(full_download_path)
            for direct_link in song_to_download['directLinks']:
                download_song_to_path(
                    song_to_download['directLinks'][direct_link], full_download_path)

        DOWNLOADED_SONGS_LIST = cache_downloaded_song(song_to_download['id'],
                                                      DOWNLOADED_SONGS_LIST,
                                                      config['BOT']['downloadedSongsCacheFile'])
        return True
    return False


def download_song_to_path(downloadLink: str, downloadPath: str):
    with requests.get(downloadLink, headers=REQUEST_HEADER, stream=True) as response:
        # Bypass Google drive virus scanning warning
        download_warning = check_for_download_warning(response)
        if download_warning:
            response = requests.get(downloadLink+'&confirm='+response.cookies[download_warning],
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
    temp_file = os.path.join(tempFolder, filename)
    patoolib.extract_archive(temp_file, verbosity=-1,
                             outdir=download_folder+'/', interactive=False)


def cache_downloaded_song(id: int, songList: list, songListFile: str):
    with open(songListFile, 'w') as filehandle:
        filehandle.writelines([str(songId) + "\n" for songId in songList])

    return songList + [id]


def check_for_download_warning(response: requests.Response):
    return next((link for link in response.cookies.get_dict() if link.startswith('download_warning')), None)


bot.run(os.getenv('DISCORD_TOKEN'))
