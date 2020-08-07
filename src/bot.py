import discord
import html
import json
from asyncio import TimeoutError
from discord.ext import commands
from dotenv import load_dotenv
from logging import getLogger, FileHandler, Formatter, DEBUG
from os import getenv
from urllib.parse import urlparse
from urllib.request import Request, urlopen

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
apiUrl: str = None

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

@bot.command(name='search', help='Make a search using a string with an optional type')
async def search(ctx, search_string: str, query_type: str = None):
    global apiUrl

    # Prevent calling before an api is added
    if not apiUrl:
        return await ctx.send('```Firstly add an api url with: $api <url>```')

    # Search request
    apiRequest = Request(
        url='{0}search?query={1}={2}'.format(apiUrl, query_type, search_string) if query_type else '{0}search?query={1}'.format(apiUrl, search_string),
        headers={'User-Agent': 'Mozilla/5.0'}
    )
    apiData = {}
    with urlopen(apiRequest) as response:
        apiData = json.loads(response.read())

    apiResultChoice = ['`{0}` {1} - {2}'.format(i, song['name'], song['artist']) for i, song in enumerate(apiData['songs'], start=1)]
    apiResponse = discord.Embed(
        title=ctx.message.author.name,
        colour=discord.Colour.blue(),
        description='\n'.join(apiResultChoice),
    )
    apiResponse.set_footer(text='Type a number to download it')
    await ctx.send(embed=apiResponse, delete_after=DEFAULT_TIMEOUT)

    # Handle response
    def check(m):
        return 0 < int(m.content) <= len(apiData['songs'])

    try:
        msg = await bot.wait_for('message', check=check, timeout=DEFAULT_TIMEOUT)
        await ctx.send('Downloading: {0}'.format(apiData['songs'][int(msg.content) - 1]['name']))
    except TimeoutError:
        pass

@bot.event
async def on_command_error(ctx, error):
    await ctx.send_help(ctx.command)


bot.run(TOKEN)