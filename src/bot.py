import discord
import json
import patoolib
import os
import requests
import requests_cache
from asyncio import TimeoutError
from cgi import parse_header
from discord.ext import commands
from dotenv import load_dotenv

# Globals
load_dotenv()
API_URL: str = os.getenv('CHORUS_API') or None
CHUNK_SIZE = 1024 * 8
DEFAULT_TIMEOUT = 15.0
DOWNLOADED_SONGS_FILE = './downloaded_songs.txt'
DOWNLOAD_PATH = os.getenv('CHORUS_DOWNLOAD_PATH') or './download'
DOWNLOAD_PATH_TEMP = './temp'
EMBED_COLOUR = discord.Colour.blue()
EXPIRE_AFTER_SECONDS = os.getenv('CHORUS_CACHE_EXPIRE_AFTER_SECONDS') or 60 * 60 * 24
REQUEST_HEADER = {'User-Agent': 'Mozilla/5.0'}

# loading Discord Token from environment variables
TOKEN = os.getenv('DISCORD_TOKEN')

# Creating bot
bot = commands.Bot(command_prefix=os.getenv('DISCORD_COMMAND_PREFIX') or '$')

# Seting up request caching
requests_cache.install_cache('chorus_cache', backend='sqlite', expire_after=EXPIRE_AFTER_SECONDS)

# Setting up paths and files
if not os.path.exists(DOWNLOAD_PATH_TEMP): os.makedirs(DOWNLOAD_PATH_TEMP)
if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)
try:
    filehandle = open(DOWNLOADED_SONGS_FILE, 'r')
    DOWNLOADED_SONGS_LIST = [int(line.rstrip('\n')) for line in filehandle]
except IOError:
    with open(DOWNLOADED_SONGS_FILE, 'w'): DOWNLOADED_SONGS_LIST = []

@bot.command(name='ping')
async def pong(ctx):
    await ctx.send('pong')

@bot.command(name='api', help='Gets or sets the api')
@commands.has_role('admin')
async def api(ctx, api_url: str=None):
    global API_URL

    if api_url:
        if not api_url.endswith('/'): api_url += '/'
        API_URL = api_url
        await ctx.send('Api url set to: %s' % api_url)
    elif API_URL:
        await ctx.send('Api url is: %s' % API_URL)
    else:
        await ctx.send_help('api')

@bot.command(name='search', help='Make a search using a string with an optional type. After that select a song by typing it\'s numerical value')
async def search(ctx, search_string: str, query_type: str = None):
    global API_URL

    # Prevent calling before an api is added
    if not API_URL: return await ctx.send('```Firstly add an api url with: $api <url>```')

    # Search request
    apiData = getApiData(API_URL, search_string, query_type)
    apiResultChoice = generateResultChoices(apiData)
    apiResponse = discord.Embed(
        title=ctx.message.author.name,
        colour=EMBED_COLOUR,
        description='\n'.join(apiResultChoice)
    )
    apiResponse.set_footer(text='Type a number to download it')
    await ctx.send(embed=apiResponse, delete_after=DEFAULT_TIMEOUT)

    # Handle response
    check = lambda message: message.content.isdigit() and 0 < int(message.content) <= len(apiData['songs']) and ctx.message.author.name == message.author.name

    try:
        msg = await bot.wait_for('message', check=check, timeout=DEFAULT_TIMEOUT)
        songToDownload = apiData['songs'][int(msg.content) - 1]

        if songToDownload['id'] in DOWNLOADED_SONGS_LIST:
            await ctx.send('Already downloaded: {0} - {1}'.format(songToDownload['name'], songToDownload['artist']))
        else:
            downloadingMsg = await ctx.send('Downloading: {0} - {1}'.format(songToDownload['name'], songToDownload['artist']))
            if downloadSong(songToDownload):
                __addDownloadedSongToList(songToDownload['id'])
                await ctx.send('Downloaded: {0} - {1}'.format(songToDownload['name'], songToDownload['artist']))
                await downloadingMsg.delete()
            else:
                await ctx.send('Error downloading: {0} - {1}'.format(songToDownload['name'], songToDownload['artist']))
    except TimeoutError:
        pass

@bot.event
async def on_command_error(ctx, error):
    print(error)
    await ctx.send("Oops! It looks like my human isn't a good programmer afterall... 🦄")

def getApiData(apiUrl: str, search_string: str, query_type: str = None):
    url=apiUrl + ('search?query={0}%3D{1}'.format(query_type, search_string) if query_type else 'search?query={0}'.format(search_string))
    return requests.get(url, headers=REQUEST_HEADER).json()

def generateResultChoices(apiData: dict):
    tierGuitar = lambda song : ' | '+'⭐'*int(song['tier_guitar']) if song['tier_guitar'] else ''
    return [
        '`{0}` {1} - {2}{3}'.format(i, song['name'], song['artist'], tierGuitar(song))
        for i, song in enumerate(apiData['songs'], start=1)
    ]

def downloadSong(songToDownload: dict):
    if 'directLinks' in songToDownload:
        if 'archive' in songToDownload['directLinks']:
            __extractArchive(__downloadSongFromArchiveOrAsSingleFiles(songToDownload, 'archive', isArchive=True))
            return True
        else:
            os.makedirs(DOWNLOAD_PATH + '/' + songToDownload['name'])
            for key in songToDownload['directLinks']:
                __downloadSongFromArchiveOrAsSingleFiles(songToDownload, key, isArchive=False)
            return True
    return False

def __downloadSongFromArchiveOrAsSingleFiles(songToDownload: dict, key: str, isArchive: bool = False):
    url=songToDownload['directLinks'][key]
    with requests.get(url, headers=REQUEST_HEADER, stream=True) as response:
        # Bypass Google drive virus scanning warning
        downloadWarning = next((key for key in response.cookies.get_dict() if key.startswith('download_warning')), None)
        if downloadWarning:
            response = requests.get(url+'&confirm='+response.cookies[downloadWarning], headers=REQUEST_HEADER, cookies=response.cookies, stream=True)
        response.raise_for_status()

        # Save response to file
        filename = __getFilenameFromContentDisposition(response.headers.get('Content-Disposition'))
        path = DOWNLOAD_PATH_TEMP + '/' + filename if isArchive else DOWNLOAD_PATH + '/' + songToDownload['name'] + '/' + filename

        with open(path, 'wb') as filehandle:
            for chunk in response.iter_content(chunk_size=CHUNK_SIZE):
                filehandle.write(chunk)
               
        del response
        return filename


def __getFilenameFromContentDisposition(cd: str):
    if not cd: return None
    _, data = parse_header(cd)
    return data['filename'] if 'filename' in data else None

def __extractArchive(file: str):
    patoolib.extract_archive(DOWNLOAD_PATH_TEMP + '/' + file, verbosity=-1, outdir=DOWNLOAD_PATH + '/', interactive=False)
    os.remove(DOWNLOAD_PATH_TEMP + '/' + file)

def __addDownloadedSongToList(id: int):
    DOWNLOADED_SONGS_LIST.append(id)
    with open(DOWNLOADED_SONGS_FILE, 'w') as filehandle:
        filehandle.writelines([str(songId) + "\n" for songId in DOWNLOADED_SONGS_LIST])

bot.run(TOKEN)