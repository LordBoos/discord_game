import calendar
import logging
import re
import time
from typing import Union

import aiohttp
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from addict import Dict
from nextcord import ActivityType, Spotify, Game, Streaming, CustomActivity, Activity, Member, User, VoiceState, TextChannel, \
    RawReactionActionEvent
from nextcord.ext import tasks
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, EVENT_HOMEASSISTANT_START)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['nextcord==2.0.0a8']

CONF_TOKEN = 'token'
CONF_MEMBERS = 'members'
CONF_CHANNELS = 'channels'
CONF_IMAGE_FORMAT = 'image_format'

DOMAIN = 'sensor'

ENTITY_ID_FORMAT = "sensor.discord_user_{}"
ENTITY_ID_CHANNEL_FORMAT = "sensor.discord_channel_{}"

app_list = []
steam_app_list = []

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_MEMBERS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Required(CONF_CHANNELS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_IMAGE_FORMAT, default='webp'): vol.In(['png', 'webp', 'jpeg', 'jpg']),
})


# noinspection PyUnusedLocal
async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    import nextcord
    token = config.get(CONF_TOKEN)
    image_format = config.get(CONF_IMAGE_FORMAT)

    intents = nextcord.Intents.all()

    bot = nextcord.Client(loop=hass.loop, intents=intents)
    await bot.login(token)

    # noinspection PyUnusedLocal
    async def async_stop_server(event):
        await bot.close()

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

    async def update_discord_entity(_watcher: DiscordAsyncMemberState, discord_member: Member):
        _watcher._state = discord_member.status
        _watcher._roles = [role.name for role in discord_member.roles]
        _watcher._display_name = discord_member.display_name
        _watcher._activity_state = None
        _watcher._game = None
        _watcher._game_state = None
        _watcher._game_details = None
        _watcher._game_image_small = None
        _watcher._game_image_large = None
        _watcher._game_image_small_text = None
        _watcher._game_image_large_text = None
        _watcher._game_image_capsule_231x87 = None
        _watcher._game_image_capsule_467x181 = None
        _watcher._game_image_capsule_616x353 = None
        _watcher._game_image_header = None
        _watcher._game_image_hero_capsule = None
        _watcher._game_image_library_600x900 = None
        _watcher._game_image_library_hero = None
        _watcher._game_image_logo = None
        _watcher._game_image_page_bg_raw = None
        _watcher._streaming = None
        _watcher._streaming_details = None
        _watcher._streaming_url = None
        _watcher._listening = None
        _watcher._listening_details = None
        _watcher._listening_url = None
        _watcher._spotify_artists = None
        _watcher._spotify_title = None
        _watcher._spotify_album = None
        _watcher._spotify_album_cover_url = None
        _watcher._spotify_track_id = None
        _watcher._spotify_duration = None
        _watcher._spotify_start = None
        _watcher._spotify_end = None
        _watcher._watching = None
        _watcher._watching_details = None
        _watcher._watching_url = None
        _watcher._custom_status = None
        _watcher._custom_emoji = None
        _watcher._voice_deaf = None
        _watcher._voice_mute = None
        _watcher._voice_self_deaf = None
        _watcher._voice_self_mute = None
        _watcher._voice_self_stream = None
        _watcher._voice_self_video = None
        _watcher._voice_afk = None
        _watcher._voice_channel = None
        if discord_member.voice is not None:
            if discord_member.voice.channel is not None:
                _watcher._voice_channel = discord_member.voice.channel.name
            else:
                _watcher._voice_channel = None
            _watcher._voice_deaf = discord_member.voice.deaf
            _watcher._voice_mute = discord_member.voice.mute
            _watcher._voice_self_deaf = discord_member.voice.self_deaf
            _watcher._voice_self_mute = discord_member.voice.self_mute
            _watcher._voice_self_stream = discord_member.voice.self_stream
            _watcher._voice_self_video = discord_member.voice.self_video
            _watcher._voice_afk = discord_member.voice.afk

        for activity in discord_member.activities:
            if activity.type == ActivityType.playing:
                await load_game_image(activity)
                _watcher._game = activity.name
                if hasattr(activity, 'state'):
                    _watcher._game_state = activity.state
                if hasattr(activity, 'details'):
                    _watcher._game_details = activity.details
                continue
            if activity.type == ActivityType.streaming:
                activity: Streaming
                _watcher._streaming = activity.name
                _watcher._streaming_details = activity.details
                _watcher._streaming_url = activity.url
                continue
            if activity.type == ActivityType.listening:
                if isinstance(activity, Spotify):
                    activity: Spotify
                    _watcher._listening = activity.title
                    _watcher._spotify_artists = ", ".join(activity.artists)
                    _watcher._spotify_title = activity.title
                    _watcher._spotify_album = activity.album
                    _watcher._spotify_album_cover_url = activity.album_cover_url
                    _watcher._spotify_track_id = activity.track_id
                    _watcher._spotify_duration = str(activity.duration)
                    _watcher._spotify_start = str(activity.start)
                    _watcher._spotify_end = str(activity.end)
                    continue
                else:
                    activity: Activity
                    _watcher._activity_state = activity.state
                    _watcher._listening = activity.name
                    _watcher._listening_details = activity.details
                    _watcher._listening_url = activity.url
                    continue
            if activity.type == ActivityType.watching:
                activity: Activity
                _watcher._activity_state = activity.state
                _watcher._watching = activity.name
                _watcher._watching_details = activity.details
                _watcher._watching_url = activity.url
                continue
            if activity.type == ActivityType.custom:
                activity: CustomActivity
                _watcher._activity_state = activity.state
                _watcher._custom_status = activity.name
                _watcher._custom_emoji = activity.emoji.name if activity.emoji else None

        _watcher.async_schedule_update_ha_state(False)

    async def update_discord_entity_user(_watcher: DiscordAsyncMemberState, discord_user: User):
        _watcher._avatar_url = discord_user.display_avatar.with_size(1024).with_static_format(image_format).__str__()
        _watcher._userid = discord_user.id
        _watcher._member = discord_user.name + '#' + discord_user.discriminator
        _watcher._user_name = discord_user.name
        _watcher.async_schedule_update_ha_state(False)

    async def load_game_image(activity: Union[Activity, Game, Streaming]):
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
        users = {"{}".format(_user): _user for _user in bot.users}
        members = {"{}".format(_member): _member for _member in list(bot.get_all_members())}
        for name, _watcher in watchers.items():
            if users.get(name) is not None:
                await update_discord_entity_user(_watcher, users.get(name))
            if members.get(name) is not None:
                await update_discord_entity(_watcher, members.get(name))
        for name, chan in channels.items():
            chan.async_schedule_update_ha_state(False)

    # noinspection PyUnusedLocal
    @bot.event
    async def on_member_update(before: Member, after: Member):
        _watcher = watchers.get("{}".format(after))
        if _watcher is not None:
            await update_discord_entity(_watcher, after)

    # noinspection PyUnusedLocal
    @bot.event
    async def on_presence_update(before: Member, after: Member):
        _watcher = watchers.get("{}".format(after))
        if _watcher is not None:
            await update_discord_entity(_watcher, after)

    # noinspection PyUnusedLocal
    @bot.event
    async def on_user_update(before: User, after: User):
        _watcher: DiscordAsyncMemberState = watchers.get("{}".format(after))
        if _watcher is not None:
            await update_discord_entity_user(_watcher, after)

    # noinspection PyUnusedLocal
    @bot.event
    async def on_voice_state_update(_member: Member, before: VoiceState, after: VoiceState):
        _watcher = watchers.get("{}".format(_member))
        if _watcher is not None:
            if after.channel is not None:
                _watcher._voice_channel = after.channel.name
            else:
                _watcher._voice_channel = None
            _watcher._voice_deaf = after.deaf
            _watcher._voice_mute = after.mute
            _watcher._voice_self_deaf = after.self_deaf
            _watcher._voice_self_mute = after.self_mute
            _watcher._voice_self_stream = after.self_stream
            _watcher._voice_self_video = after.self_video
            _watcher._voice_afk = after.afk
            _watcher.async_schedule_update_ha_state(False)

    @bot.event
    async def on_raw_reaction_add(payload: RawReactionActionEvent):
        channel_id = payload.channel_id
        channel: TextChannel = await bot.fetch_channel(channel_id)
        member: Member = payload.member
        chan = channels.get("{}".format(channel))
        if chan:
            chan._state = member.display_name
            chan._last_user = member.display_name
            chan.async_schedule_update_ha_state(False)

    watchers = {}
    for member in config.get(CONF_MEMBERS):
        if re.match(r"^\d{,20}", member):  # Up to 20 digits because 2^64 (snowflake-length) is 20 digits long
            user = await bot.fetch_user(member)
            if user:
                watcher: DiscordAsyncMemberState = \
                    DiscordAsyncMemberState(hass, bot, "{}#{}".format(user.name, user.discriminator), user.id)
                watchers[watcher.name] = watcher

    channels = {}
    for channel in config.get(CONF_CHANNELS):
        if re.match(r"^[0-9]{,20}", channel):  # Up to 20 digits because 2^64 (snowflake-length) is 20 digits long
            chan: TextChannel = await bot.fetch_channel(channel)
            if chan:
                ch: DiscordAsyncReactionState = DiscordAsyncReactionState(hass, bot, chan.name, chan.id)
                channels[ch.name] = ch

    if len(watchers) > 0:
        async_add_entities(watchers.values())
        async_add_entities(channels.values())
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
        self._spotify_artists = None
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
        self.entity_id = ENTITY_ID_FORMAT.format(self._userid)

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def native_value(self) -> str:
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
    def extra_state_attributes(self):
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
            'spotify_artist': self._spotify_artists,
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


class DiscordAsyncReactionState(SensorEntity):
    def __init__(self, hass, client, channel, channelid):
        self._channel_name = channel
        self._channel_id = channelid
        self._hass = hass
        self._client = client
        self._state = 'unknown'
        self._last_user = None
        self.entity_id = ENTITY_ID_CHANNEL_FORMAT.format(self._channel_id)

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def state(self) -> str:
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return ENTITY_ID_CHANNEL_FORMAT.format(self._channel_id)

    @property
    def name(self):
        return self._channel_name

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            'last_user': self._last_user
        }
