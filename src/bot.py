import discord
import json
import patoolib
import requests
import os
from asyncio import TimeoutError
from cgi import parse_header
from discord.ext import commands
from dotenv import load_dotenv
from logging import getLogger, FileHandler, Formatter, DEBUG

# Setting up the logger
logger = getLogger('discord')
logger.setLevel(DEBUG)
handler = FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# loading Discord Token from environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Creating bot
bot = commands.Bot(command_prefix=os.getenv('DISCORD_COMMAND_PREFIX') or '$')

# Globals
DEFAULT_TIMEOUT = 15.0
DOWNLOAD_PATH = os.getenv('DOWNLOAD_PATH') or './download'
DOWNLOAD_PATH_TEMP = './temp'
EMBED_COLOUR = discord.Colour.blue()
REQUEST_HEADER = {'User-Agent': 'Mozilla/5.0'}
API_URL: str = os.getenv('CHORUS_API') or None

if not os.path.exists(DOWNLOAD_PATH_TEMP): os.makedirs(DOWNLOAD_PATH_TEMP)
if not os.path.exists(DOWNLOAD_PATH): os.makedirs(DOWNLOAD_PATH)

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
        await ctx.send('Downloading: {0}'.format(songToDownload['name']))
        downloadSong(songToDownload)
        await ctx.send('Downloaded: {0}'.format(songToDownload['name']))
    except TimeoutError:
        pass

@bot.event
async def on_command_error(ctx, error):
    await ctx.send(error)

def getApiData(apiUrl: str, search_string: str, query_type: str = None):
    url='{0}search?query={1}%3D{2}'.format(apiUrl, query_type, search_string) if query_type else '{0}search?query={1}'.format(apiUrl, search_string)

    with requests.get(url, headers=REQUEST_HEADER) as response:
        return json.loads(response.content)

def generateResultChoices(apiData):
    tierGuitar = lambda song : ' | '+'⭐'*int(song['tier_guitar']) if song['tier_guitar'] else ''
    return [
        '`{0}` {1} - {2}{3}'.format(i, song['name'], song['artist'], tierGuitar(song))
        for i, song in enumerate(apiData['songs'], start=1)
    ]

def downloadSong(songToDownload: dict):
    if 'directLinks' in songToDownload:
        if 'archive' in songToDownload['directLinks']:
            __extractArchive(__downloadSongFromArchiveOrAsSingleFiles(songToDownload, 'archive', isArchive=True))
        else:
            if not os.path.exists(DOWNLOAD_PATH + '/' + songToDownload['name']): os.makedirs(DOWNLOAD_PATH + '/' + songToDownload['name'])
            for key in songToDownload['directLinks']:
                __downloadSongFromArchiveOrAsSingleFiles(songToDownload, key, isArchive=False)

def __downloadSongFromArchiveOrAsSingleFiles(songToDownload: dict, key: str, isArchive: bool = False):
    url=songToDownload['directLinks'][key]
    with requests.get(url, headers=REQUEST_HEADER) as response:
        filename = __getFilenameFromContentDisposition(response.headers.get('Content-Disposition'))
        path = DOWNLOAD_PATH_TEMP + '/' + filename if isArchive else DOWNLOAD_PATH + '/' + songToDownload['name'] + '/' + filename
        with open(path, 'wb') as filehandle:
            if filehandle.write(response.content) > 0: return filename


def __getFilenameFromContentDisposition(cd):
    if not cd: return None
    _, data = parse_header(cd)
    return data['filename'] if 'filename' in data else None

def __extractArchive(file: str):
    # songDirectory, fileExtension = path.splitext(file)
    # if not path.exists(DOWNLOAD_PATH + '/' + songDirectory): makedirs(DOWNLOAD_PATH + '/' + songDirectory)
    patoolib.extract_archive(DOWNLOAD_PATH_TEMP + '/' + file, verbosity=-1, outdir=DOWNLOAD_PATH + '/', interactive=False)
    os.remove(DOWNLOAD_PATH_TEMP + '/' + file)

bot.run(TOKEN)