import calendar
import logging
import re
import time
from typing import Union

import aiohttp
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from addict import Dict
from discord import ActivityType, Spotify, Game, Streaming, CustomActivity, Activity, Member, User, VoiceState
from discord.ext import tasks
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, EVENT_HOMEASSISTANT_START)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['discord.py==1.5.1']

CONF_TOKEN = 'token'
CONF_MEMBERS = 'members'
CONF_IMAGE_FORMAT = 'image_format'

DOMAIN = 'sensor'

ENTITY_ID_FORMAT = "sensor.discord_user_{}"

app_list = []
steam_app_list = []

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_MEMBERS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_IMAGE_FORMAT, default='webp'): vol.In(['png', 'webp', 'jpeg', 'jpg']),
})


# noinspection PyUnusedLocal
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    import discord
    token = config.get(CONF_TOKEN)
    image_format = config.get(CONF_IMAGE_FORMAT)

    intents = discord.Intents.default()
    intents.members = True
    intents.presences = True

    bot = discord.Client(loop=hass.loop, intents=intents)
    await bot.login(token)

    # noinspection PyUnusedLocal
    async def async_stop_server(event):
        await bot.logout()

    # noinspection PyUnusedLocal
    async def start_server(event):
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_server)
        await load_application_list_cache()
        await bot.start(token)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_server)

    @tasks.loop(hours=1)
    async def refresh_application_lists():
        await load_application_list_cache()

    refresh_application_lists.start()

    async def load_application_list_cache():
        await load_discord_application_list()
        await load_steam_application_list()

    async def load_discord_application_list():
        async with aiohttp.ClientSession() as session:
            _LOGGER.debug("Loading Discord detectable applications")
            async with session.get("https://discord.com/api/v9/applications/detectable") as response:
                global app_list
                app_list = await response.json()
            _LOGGER.debug("Loading Discord detectable applications finished")

    async def load_steam_application_list():
        async with aiohttp.ClientSession() as steam_session:
            _LOGGER.debug("Loading Steam detectable applications")
            async with steam_session.get("https://api.steampowered.com/ISteamApps/GetAppList/v2/") as steam_response:
                steam_app_list_response = Dict(await steam_response.json())
                global steam_app_list
                steam_app_list = steam_app_list_response['applist']['apps']
                _LOGGER.debug("Loading Steam detectable applications finished")

    # noinspection PyUnusedLocal
    @bot.event
    async def on_error(error, *args, **kwargs):
        raise

    async def update_discord_entity(watcher: DiscordAsyncMemberState, discord_member: Member):
        watcher._state = discord_member.status
        watcher._roles = [role.name for role in discord_member.roles]
        watcher._display_name = discord_member.display_name
        watcher._activity_state = None
        watcher._game = None
        watcher._game_state = None
        watcher._game_details = None
        watcher._game_image_small = None
        watcher._game_image_large = None
        watcher._game_image_small_text = None
        watcher._game_image_large_text = None
        watcher._game_image_capsule_231x87 = None
        watcher._game_image_capsule_467x181 = None
        watcher._game_image_capsule_616x353 = None
        watcher._game_image_header = None
        watcher._game_image_hero_capsule = None
        watcher._game_image_library_600x900 = None
        watcher._game_image_library_hero = None
        watcher._game_image_logo = None
        watcher._game_image_page_bg_raw = None
        watcher._streaming = None
        watcher._streaming_details = None
        watcher._streaming_url = None
        watcher._listening = None
        watcher._listening_details = None
        watcher._listening_url = None
        watcher._spotify_artists = None
        watcher._spotify_title = None
        watcher._spotify_album = None
        watcher._spotify_album_cover_url = None
        watcher._spotify_track_id = None
        watcher._spotify_duration = None
        watcher._spotify_start = None
        watcher._spotify_end = None
        watcher._watching = None
        watcher._watching_details = None
        watcher._watching_url = None
        watcher._custom_status = None
        watcher._custom_emoji = None
        watcher._voice_deaf = None
        watcher._voice_mute = None
        watcher._voice_self_deaf = None
        watcher._voice_self_mute = None
        watcher._voice_self_stream = None
        watcher._voice_self_video = None
        watcher._voice_afk = None
        watcher._voice_channel = None
        if discord_member.voice is not None:
            if discord_member.voice.channel is not None:
                watcher._voice_channel = discord_member.voice.channel.name
            else:
                watcher._voice_channel = None
            watcher._voice_deaf = discord_member.voice.deaf
            watcher._voice_mute = discord_member.voice.mute
            watcher._voice_self_deaf = discord_member.voice.self_deaf
            watcher._voice_self_mute = discord_member.voice.self_mute
            watcher._voice_self_stream = discord_member.voice.self_stream
            watcher._voice_self_video = discord_member.voice.self_video
            watcher._voice_afk = discord_member.voice.afk

        for activity in discord_member.activities:
            if activity.type == ActivityType.playing:
                await load_game_image(activity)
                watcher._game = activity.name
                if hasattr(activity, 'state'):
                    watcher._game_state = activity.state
                if hasattr(activity, 'details'):
                    watcher._game_details = activity.details
                continue
            if activity.type == ActivityType.streaming:
                activity: Streaming
                watcher._streaming = activity.name
                watcher._streaming_details = activity.details
                watcher._streaming_url = activity.url
                continue
            if activity.type == ActivityType.listening:
                if isinstance(activity, Spotify):
                    activity: Spotify
                    watcher._listening = activity.title
                    watcher._spotify_artists = ", ".join(activity.artists)
                    watcher._spotify_title = activity.title
                    watcher._spotify_album = activity.album
                    watcher._spotify_album_cover_url = activity.album_cover_url
                    watcher._spotify_track_id = activity.track_id
                    watcher._spotify_duration = str(activity.duration)
                    watcher._spotify_start = str(activity.start)
                    watcher._spotify_end = str(activity.end)
                    continue
                else:
                    activity: Activity
                    watcher._activity_state = activity.state
                    watcher._listening = activity.name
                    watcher._listening_details = activity.details
                    watcher._listening_url = activity.url
                    continue
            if activity.type == ActivityType.watching:
                activity: Activity
                watcher._activity_state = activity.state
                watcher._watching = activity.name
                watcher._watching_details = activity.details
                watcher._watching_url = activity.url
                continue
            if activity.type == ActivityType.custom:
                activity: CustomActivity
                watcher._activity_state = activity.state
                watcher._custom_status = activity.name
                watcher._custom_emoji = activity.emoji.name if activity.emoji else None

        watcher.async_schedule_update_ha_state(False)

    async def update_discord_entity_user(watcher: DiscordAsyncMemberState, discord_user: User):
        watcher._avatar_url = discord_user.avatar_url_as(format=None, static_format=image_format, size=1024).__str__()
        watcher._userid = discord_user.id
        watcher._member = discord_user.name + '#' + discord_user.discriminator
        watcher._user_name = discord_user.name
        watcher.async_schedule_update_ha_state(False)

    async def load_game_image(activity: Union[Activity, Game]):
        # try:
        if hasattr(activity, 'large_image_url'):
            watcher._game_image_small = activity.small_image_url
            watcher._game_image_large = activity.large_image_url
            watcher._game_image_small_text = activity.small_image_text
            watcher._game_image_large_text = activity.large_image_text
        if hasattr(activity, 'application_id'):
            app_id = activity.application_id
            discord_app = list(filter(lambda app: app['id'] == str(app_id), app_list))
            if discord_app:
                _LOGGER.debug("FOUND discord app by application_id = %s", discord_app)
                watcher._game_image_small = f"https://cdn.discordapp.com/app-icons/{discord_app[0]['id']}/{discord_app[0]['icon']}.png"
        discord_app_by_name = list(filter(lambda app: app['name'] == str(activity.name), app_list))
        if discord_app_by_name:
            _LOGGER.debug("FOUND discord app by name = %s", discord_app_by_name)
            watcher._game_image_small = \
                f"https://cdn.discordapp.com/app-icons/{discord_app_by_name[0]['id']}/{discord_app_by_name[0]['icon']}.png"
        steam_app_by_name = list(filter(lambda steam_app: steam_app['name'] == str(activity.name), steam_app_list))
        if steam_app_by_name:
            steam_app_id = steam_app_by_name[0]["appid"]
            _LOGGER.debug("FOUND Steam app by name = %s", steam_app_by_name[0])
            timestamp = calendar.timegm(time.gmtime())
            game_image_capsule_231x87 = \
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/capsule_231x87.jpg?t={timestamp}"
            game_image_capsule_467x181 = \
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/capsule_467x181.jpg?t={timestamp}"
            game_image_capsule_616x353 = \
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/capsule_616x353.jpg?t={timestamp}"
            game_image_header = \
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/header.jpg?t={timestamp}"
            game_image_hero_capsule = \
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/hero_capsule.jpg?t={timestamp}"
            game_image_library_600x900 = \
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/library_600x900.jpg?t={timestamp}"
            game_image_library_hero = \
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/library_hero.jpg?t={timestamp}"
            game_image_logo = \
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/logo.jpg?t={timestamp}"
            game_image_page_bg_raw = \
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/page_bg_raw.jpg?t={timestamp}"

            if await check_resource_exists(game_image_capsule_231x87):
                watcher._game_image_capsule_231x87 = game_image_capsule_231x87
            if await check_resource_exists(game_image_capsule_467x181):
                watcher._game_image_capsule_467x181 = game_image_capsule_467x181
            if await check_resource_exists(game_image_capsule_616x353):
                watcher._game_image_capsule_616x353 = game_image_capsule_616x353
            if await check_resource_exists(game_image_header):
                watcher._game_image_header = game_image_header
            if await check_resource_exists(game_image_hero_capsule):
                watcher._game_image_hero_capsule = game_image_hero_capsule
            if await check_resource_exists(game_image_library_600x900):
                watcher._game_image_library_600x900 = game_image_library_600x900
            if await check_resource_exists(game_image_library_hero):
                watcher._game_image_library_hero = game_image_library_hero
            if await check_resource_exists(game_image_logo):
                watcher._game_image_logo = game_image_logo
            if await check_resource_exists(game_image_page_bg_raw):
                watcher._game_image_page_bg_raw = game_image_page_bg_raw

    async def check_resource_exists(url):
        async with aiohttp.ClientSession() as session:
            _LOGGER.debug("Checking if web resource [%s] exists", url)
            async with session.head(url) as response:
                _LOGGER.debug("Resource [%s] response status = %s", url, response.status)
                return response.status == 200

    @bot.event
    async def on_ready():
        users = {"{}".format(user): user for user in bot.users}
        members = {"{}".format(member): member for member in list(bot.get_all_members())}
        for name, watcher in watchers.items():
            if users.get(name) is not None:
                await update_discord_entity_user(watcher, users.get(name))
            if members.get(name) is not None:
                await update_discord_entity(watcher, members.get(name))

    # noinspection PyUnusedLocal
    @bot.event
    async def on_member_update(before: Member, after: Member):
        watcher = watchers.get("{}".format(after))
        if watcher is not None:
            await update_discord_entity(watcher, after)

    # noinspection PyUnusedLocal
    @bot.event
    async def on_user_update(before: User, after: User):
        watcher: DiscordAsyncMemberState = watchers.get("{}".format(after))
        if watcher is not None:
            await update_discord_entity_user(watcher, after)

    # noinspection PyUnusedLocal
    @bot.event
    async def on_voice_state_update(member: Member, before: VoiceState, after: VoiceState):
        watcher = watchers.get("{}".format(member))
        if watcher is not None:
            if after.channel is not None:
                watcher._voice_channel = after.channel.name
            else:
                watcher._voice_channel = None
            watcher._voice_deaf = after.deaf
            watcher._voice_mute = after.mute
            watcher._voice_self_deaf = after.self_deaf
            watcher._voice_self_mute = after.self_mute
            watcher._voice_self_stream = after.self_stream
            watcher._voice_self_video = after.self_video
            watcher._voice_afk = after.afk
            watcher.async_schedule_update_ha_state(False)

    watchers = {}
    for member in config.get(CONF_MEMBERS):
        if re.match(r"^[0-9]{,20}", member):  # Up to 20 digits because 2^64 (snowflake-length) is 20 digits long
            user = await bot.fetch_user(member)
            if user:
                watcher: DiscordAsyncMemberState = \
                    DiscordAsyncMemberState(hass, bot, "{}#{}".format(user.name, user.discriminator), user.id)
                watchers[watcher.name] = watcher
    if len(watchers) > 0:
        async_add_entities(watchers.values())
        return True
    else:
        return False


class DiscordAsyncMemberState(SensorEntity):
    def __init__(self, hass, client, member, userid):
        self._member = member
        self._userid = userid
        self._hass = hass
        self._client = client
        self._state = 'unknown'
        self._activity_state = 'unknown'
        self._user_name = None
        self._display_name = None
        self._roles = None
        self._game = None
        self._game_state = None
        self._game_details = None
        self._game_image_small = None
        self._game_image_large = None
        self._game_image_small_text = None
        self._game_image_large_text = None
        self._game_image_capsule_231x87 = None
        self._game_image_capsule_467x181 = None
        self._game_image_capsule_616x353 = None
        self._game_image_header = None
        self._game_image_hero_capsule = None
        self._game_image_library_600x900 = None
        self._game_image_library_hero = None
        self._game_image_logo = None
        self._game_image_page_bg_raw = None
        self._streaming = None
        self._streaming_url = None
        self._streaming_details = None
        self._listening = None
        self._listening_url = None
        self._listening_details = None
        self._spotify_artist = None
        self._spotify_title = None
        self._spotify_album = None
        self._spotify_album_cover_url = None
        self._spotify_track_id = None
        self._spotify_duration = None
        self._spotify_start = None
        self._spotify_end = None
        self._watching = None
        self._watching_url = None
        self._watching_details = None
        self._avatar_url = None
        self._custom_status = None
        self._custom_emoji = None
        self._voice_channel = None
        self._voice_deaf = None
        self._voice_mute = None
        self._voice_self_deaf = None
        self._voice_self_mute = None
        self._voice_self_stream = None
        self._voice_self_video = None
        self._voice_afk = None

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def state(self) -> str:
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return ENTITY_ID_FORMAT.format(self._userid)

    @property
    def name(self):
        return self._member

    @property
    def entity_picture(self):
        return self._avatar_url

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            'avatar_url': self._avatar_url,
            'activity_state': self._activity_state,
            'user_id': self._userid,
            'user_name': self._user_name,
            'display_name': self._display_name,
            'roles': self._roles,
            'game': self._game,
            'game_state': self._game_state,
            'game_details': self._game_details,
            'game_image_small': self._game_image_small,
            'game_image_large': self._game_image_large,
            'game_image_small_text': self._game_image_small_text,
            'game_image_large_text': self._game_image_large_text,
            'game_image_capsule_231x87': self._game_image_capsule_231x87,
            'game_image_capsule_467x181': self._game_image_capsule_467x181,
            'game_image_capsule_616x353': self._game_image_capsule_616x353,
            'game_image_header': self._game_image_header,
            'game_image_hero_capsule': self._game_image_hero_capsule,
            'game_image_library_600x900': self._game_image_library_600x900,
            'game_image_library_hero': self._game_image_library_hero,
            'game_image_logo': self._game_image_logo,
            'game_image_page_bg_raw': self._game_image_page_bg_raw,
            'streaming': self._streaming,
            'streaming_url': self._streaming_url,
            'streaming_details': self._streaming_details,
            'listening': self._listening,
            'listening_url': self._listening_url,
            'listening_details': self._listening_details,
            'spotify_artist': self._spotify_artist,
            'spotify_title': self._spotify_title,
            'spotify_album': self._spotify_album,
            'spotify_album_cover_url': self._spotify_album_cover_url,
            'spotify_track_id': self._spotify_track_id,
            'spotify_duration': self._spotify_duration,
            'spotify_start': self._spotify_start,
            'spotify_end': self._spotify_end,
            'watching': self._watching,
            'watching_url': self._watching_url,
            'watching_details': self._watching_details,
            'custom_status': self._custom_status,
            'custom_emoji': self._custom_emoji,
            'voice_channel': self._voice_channel,
            'voice_server_deafened': self._voice_deaf,
            'voice_server_muted': self._voice_mute,
            'voice_self_deafened': self._voice_self_deaf,
            'voice_self_muted': self._voice_self_mute,
            'voice_streaming': self._voice_self_stream,
            'voice_broadcasting_video': self._voice_self_video,
            'voice_afk': self._voice_afk
        }
