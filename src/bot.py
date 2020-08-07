import discord
import html
import json
import patoolib
from asyncio import TimeoutError
from cgi import parse_header
from discord.ext import commands
from dotenv import load_dotenv
from logging import getLogger, FileHandler, Formatter, DEBUG
from os import getenv, path, makedirs, remove
from urllib.parse import urlparse
from urllib.request import Request, urlopen, urlretrieve

# Setting up the logger
logger = getLogger('discord')
logger.setLevel(DEBUG)
handler = FileHandler(filename='discord.log', encoding='utf-8', mode='w')
handler.setFormatter(Formatter('%(asctime)s:%(levelname)s:%(name)s: %(message)s'))
logger.addHandler(handler)

# loading Discord Token from environment variables
load_dotenv()
TOKEN = getenv('DISCORD_TOKEN')

# Creating bot
bot = commands.Bot(command_prefix='$')

# Globals
DEFAULT_TIMEOUT = 15.0
DOWNLOAD_PATH = './download'
DOWNLOAD_PATH_TEMP = './temp'
EMBED_COLOUR = discord.Colour.blue()
REQUEST_HEADER = {'User-Agent': 'Mozilla/5.0'}
apiUrl: str = None

if not path.exists(DOWNLOAD_PATH_TEMP): makedirs(DOWNLOAD_PATH_TEMP)
if not path.exists(DOWNLOAD_PATH): makedirs(DOWNLOAD_PATH)

@bot.command(name='ping')
async def pong(ctx):
    await ctx.send('pong')

@bot.command(name='api', help='Gets or sets the api')
@commands.has_role('admin')
async def api(ctx, api_url: str=None):
    global apiUrl

    if api_url:
        if not api_url.endswith('/'): api_url += '/'
        apiUrl = api_url
        await ctx.send('Api url set to: %s' % api_url)
    elif apiUrl:
        await ctx.send('Api url is: %s' % apiUrl)
    else:
        await ctx.send_help('api')

@bot.command(name='search', help='Make a search using a string with an optional type. After that select a song by typing it\'s numerical value')
async def search(ctx, search_string: str, query_type: str = None):
    global apiUrl

    # Prevent calling before an api is added
    if not apiUrl: return await ctx.send('```Firstly add an api url with: $api <url>```')

    # Search request
    apiData = getApiData(apiUrl, search_string, query_type)
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
    apiRequest = Request(
        url='{0}search?query={1}%3D{2}'.format(apiUrl, query_type, search_string) if query_type else '{0}search?query={1}'.format(apiUrl, search_string),
        headers=REQUEST_HEADER
    )
    with urlopen(apiRequest) as response:
        return json.loads(response.read())

def generateResultChoices(apiData):
    tierGuitar = lambda song : ' | '+'⭐'*int(song['tier_guitar']) if song['tier_guitar'] else ''
    return [
        '`{0}` {1} - {2}{3}'.format(i, song['name'], song['artist'], tierGuitar(song))
        for i, song in enumerate(apiData['songs'], start=1)
    ]

def downloadSong(songToDownload: dict):
    if songToDownload['directLinks'] and songToDownload['directLinks']['archive']:
        request = Request(
            url=songToDownload['directLinks']['archive'],
            headers=REQUEST_HEADER
        )

        with urlopen(request) as file:
            contentDisposition = file.info()['Content-Disposition']
            type, data = parse_header(contentDisposition)
            with open(DOWNLOAD_PATH_TEMP + '/' + data['filename'], 'wb') as filehandle:
                if filehandle.write(file.read()): extractArchive(data['filename'])
    else:
        pass

def extractArchive(file: str):
    # songDirectory, fileExtension = path.splitext(file)
    # if not path.exists(DOWNLOAD_PATH + '/' + songDirectory): makedirs(DOWNLOAD_PATH + '/' + songDirectory)
    patoolib.extract_archive(DOWNLOAD_PATH_TEMP + '/' + file, verbosity=-1, outdir=DOWNLOAD_PATH + '/', interactive=False)
    remove(DOWNLOAD_PATH_TEMP + '/' + file)

bot.run(TOKEN)