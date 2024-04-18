import asyncio
import calendar
import logging
import re
import time
from typing import Union

import aiohttp
import homeassistant.helpers.config_validation as cv
import validators
import voluptuous as vol
from addict import Dict
from homeassistant import config_entries, core
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP)
from homeassistant.helpers.entity import DeviceInfo
from nextcord import ActivityType, Spotify, Game, Streaming, CustomActivity, Activity, Member, User, VoiceState, RawReactionActionEvent
from nextcord.abc import GuildChannel
from nextcord.ext import tasks

from .const import DOMAIN, CONF_MEMBERS, CONF_CHANNELS, CONF_IMAGE_FORMAT

_LOGGER = logging.getLogger(__name__)

ENTITY_ID_FORMAT = "sensor.discord_user_{}"
ENTITY_ID_CHANNEL_FORMAT = "sensor.discord_channel_{}"

steam_app_list = []

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ACCESS_TOKEN): cv.string,
    vol.Required(CONF_MEMBERS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Required(CONF_CHANNELS, default=[]): vol.All(cv.ensure_list, [cv.string]),
    vol.Optional(CONF_IMAGE_FORMAT, default='webp'): vol.In(['png', 'webp', 'jpeg', 'jpg']),
})

SENSORS = ["user_name", "display_name", "roles", "game", "game_state", "game_details", "game_image_small", "game_image_large",
           "game_image_small_text", "game_image_large_text", "game_image_capsule_231x87", "game_image_capsule_467x181",
           "game_image_capsule_616x353", "game_image_header", "game_image_hero_capsule", "game_image_library_600x900", "game_image_library_hero",
           "game_image_logo", "game_image_page_bg_raw", "streaming", "streaming_url", "streaming_details", "listening", "listening_url",
           "listening_details", "spotify_artists", "spotify_title", "spotify_album", "spotify_album_cover_url", "spotify_track_id",
           "spotify_duration", "spotify_start", "spotify_end", "watching", "watching_url", "watching_details", "avatar_url", "custom_status",
           "custom_emoji", "voice_channel", "voice_deaf", "voice_mute", "voice_self_deaf", "voice_self_mute", "voice_self_stream",
           "voice_self_video", "voice_afk"]


async def async_setup_entry(
        hass: core.HomeAssistant,
        config_entry: config_entries.ConfigEntry,
        async_add_entities,
) -> None:
    """Setup sensors from a config entry created in the integrations UI."""
    config = hass.data[DOMAIN][config_entry.entry_id]
    import nextcord
    token = config.get(CONF_ACCESS_TOKEN)
    image_format = config.get(CONF_IMAGE_FORMAT)

    bot = nextcord.Client(loop=hass.loop, intents=nextcord.Intents.all())
    await bot.login(token)

    # noinspection PyUnusedLocal
    async def async_stop_server(event):
        await bot.close()

    def task_callback(task: asyncio.Task):
        # placeholder
        pass

    # noinspection PyUnusedLocal
    async def start_server(event):
        _LOGGER.debug("Starting server - config flow")
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_server)
        await load_application_list_cache()
        task = asyncio.create_task(bot.start(token))
        task.add_done_callback(task_callback)

    hass.bus.async_listen_once("discord_game_setup_finished", start_server)

    @tasks.loop(hours=1)
    async def refresh_application_lists():
        await load_application_list_cache()

    refresh_application_lists.start()

    async def load_application_list_cache():
        await load_steam_application_list()

    async def load_steam_application_list():
        async with aiohttp.ClientSession() as steam_session:
            _LOGGER.debug("Loading Steam detectable applications - config_flow")
            async with steam_session.get("https://api.steampowered.com/ISteamApps/GetAppList/v2/") as steam_response:
                steam_app_list_response = Dict(await steam_response.json())
                global steam_app_list
                steam_app_list = steam_app_list_response['applist']['apps']
                _LOGGER.debug("Loading Steam detectable applications finished - config_flow")

    # noinspection PyUnusedLocal
    @bot.event
    async def on_error(error, *args, **kwargs):
        raise

    async def update_discord_entity(_watcher: DiscordAsyncMemberState, discord_member: Member):
        _watcher._state = discord_member.status
        _watcher.roles = [role.name for role in discord_member.roles]
        _watcher.display_name = discord_member.display_name
        _watcher.activity_state = None
        _watcher.game = None
        _watcher.game_state = None
        _watcher.game_details = None
        _watcher.game_image_small = None
        _watcher.game_image_large = None
        _watcher.game_image_small_text = None
        _watcher.game_image_large_text = None
        _watcher.game_image_capsule_231x87 = None
        _watcher.game_image_capsule_467x181 = None
        _watcher.game_image_capsule_616x353 = None
        _watcher.game_image_header = None
        _watcher.game_image_hero_capsule = None
        _watcher.game_image_library_600x900 = None
        _watcher.game_image_library_hero = None
        _watcher.game_image_logo = None
        _watcher.game_image_page_bg_raw = None
        _watcher.streaming = None
        _watcher.streaming_details = None
        _watcher.streaming_url = None
        _watcher.listening = None
        _watcher.listening_details = None
        _watcher.listening_url = None
        _watcher.spotify_artists = None
        _watcher.spotify_title = None
        _watcher.spotify_album = None
        _watcher.spotify_album_cover_url = None
        _watcher.spotify_track_id = None
        _watcher.spotify_duration = None
        _watcher.spotify_start = None
        _watcher.spotify_end = None
        _watcher.watching = None
        _watcher.watching_details = None
        _watcher.watching_url = None
        _watcher.custom_status = None
        _watcher.custom_emoji = None
        _watcher.voice_deaf = None
        _watcher.voice_mute = None
        _watcher.voice_self_deaf = None
        _watcher.voice_self_mute = None
        _watcher.voice_self_stream = None
        _watcher.voice_self_video = None
        _watcher.voice_afk = None
        _watcher.voice_channel = None
        if discord_member.voice is not None:
            if discord_member.voice.channel is not None:
                _watcher.voice_channel = discord_member.voice.channel.name
            else:
                _watcher.voice_channel = None
            _watcher.voice_deaf = discord_member.voice.deaf
            _watcher.voice_mute = discord_member.voice.mute
            _watcher.voice_self_deaf = discord_member.voice.self_deaf
            _watcher.voice_self_mute = discord_member.voice.self_mute
            _watcher.voice_self_stream = discord_member.voice.self_stream
            _watcher.voice_self_video = discord_member.voice.self_video
            _watcher.voice_afk = discord_member.voice.afk

        for activity in discord_member.activities:
            if activity.type == ActivityType.playing:
                await load_game_image(_watcher, activity)
                _watcher.game = activity.name
                if hasattr(activity, 'state'):
                    _watcher.game_state = activity.state
                if hasattr(activity, 'details'):
                    _watcher.game_details = activity.details
                continue
            if activity.type == ActivityType.streaming:
                activity: Streaming
                _watcher.streaming = activity.name
                _watcher.streaming_details = activity.details
                _watcher.streaming_url = activity.url
                continue
            if activity.type == ActivityType.listening:
                if isinstance(activity, Spotify):
                    activity: Spotify
                    _watcher.listening = activity.title
                    _watcher.spotify_artists = ", ".join(activity.artists)
                    _watcher.spotify_title = activity.title
                    _watcher.spotify_album = activity.album
                    _watcher.spotify_album_cover_url = activity.album_cover_url
                    _watcher.spotify_track_id = activity.track_id
                    _watcher.spotify_duration = str(activity.duration)
                    _watcher.spotify_start = str(activity.start)
                    _watcher.spotify_end = str(activity.end)
                    continue
                else:
                    activity: Activity
                    _watcher.activity_state = activity.state
                    _watcher.listening = activity.name
                    _watcher.listening_details = activity.details
                    _watcher.listening_url = activity.url
                    continue
            if activity.type == ActivityType.watching:
                activity: Activity
                _watcher.activity_state = activity.state
                _watcher.watching = activity.name
                _watcher.watching_details = activity.details
                _watcher.watching_url = activity.url
                continue
            if activity.type == ActivityType.custom:
                activity: CustomActivity
                _watcher.activity_state = activity.state
                _watcher.custom_status = activity.name
                _watcher.custom_emoji = activity.emoji.name if activity.emoji else None

        _watcher.async_schedule_update_ha_state(False)

    async def update_discord_entity_user(_watcher: DiscordAsyncMemberState, discord_user: User):
        _watcher.avatar_url = discord_user.display_avatar.with_size(1024).with_static_format(image_format).__str__()
        _watcher.userid = discord_user.id
        _watcher.member = discord_user.name
        _watcher.user_name = discord_user.global_name
        _watcher.async_schedule_update_ha_state(False)

    async def load_game_image(_watcher: DiscordAsyncMemberState, activity: Union[Activity, Game, Streaming]):
        # try:
        if hasattr(activity, 'large_image_url'):
            _watcher.game_image_small = activity.small_image_url
            _watcher.game_image_large = activity.large_image_url
            _watcher.game_image_small_text = activity.small_image_text
            _watcher.game_image_large_text = activity.large_image_text
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
            game_image_logo_png = \
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/logo.png?t={timestamp}"
            game_image_page_bg_raw = \
                f"https://cdn.cloudflare.steamstatic.com/steam/apps/{steam_app_id}/page_bg_raw.jpg?t={timestamp}"

            if await check_resource_exists(game_image_capsule_231x87):
                _watcher.game_image_capsule_231x87 = game_image_capsule_231x87
            if await check_resource_exists(game_image_capsule_467x181):
                _watcher.game_image_capsule_467x181 = game_image_capsule_467x181
            if await check_resource_exists(game_image_capsule_616x353):
                _watcher.game_image_capsule_616x353 = game_image_capsule_616x353
            if await check_resource_exists(game_image_header):
                _watcher.game_image_header = game_image_header
            if await check_resource_exists(game_image_hero_capsule):
                _watcher.game_image_hero_capsule = game_image_hero_capsule
            if await check_resource_exists(game_image_library_600x900):
                _watcher.game_image_library_600x900 = game_image_library_600x900
            if await check_resource_exists(game_image_library_hero):
                _watcher.game_image_library_hero = game_image_library_hero
            if await check_resource_exists(game_image_logo):
                _watcher.game_image_logo = game_image_logo
            if await check_resource_exists(game_image_logo_png):
                _watcher.game_image_logo = game_image_logo_png
            if await check_resource_exists(game_image_page_bg_raw):
                _watcher.game_image_page_bg_raw = game_image_page_bg_raw

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
                for sensor in _watcher.sensors.values():
                    sensor.async_schedule_update_ha_state(False)
        for name, _chan in channels.items():
            _chan.async_schedule_update_ha_state(False)

    # noinspection PyUnusedLocal
    @bot.event
    async def on_member_update(before: Member, after: Member):
        _watcher = watchers.get("{}".format(after))
        if _watcher is not None:
            await update_discord_entity(_watcher, after)
            for sensor in _watcher.sensors.values():
                sensor.async_schedule_update_ha_state(False)

    # noinspection PyUnusedLocal
    @bot.event
    async def on_presence_update(before: Member, after: Member):
        _watcher = watchers.get("{}".format(after))
        if _watcher is not None:
            await update_discord_entity(_watcher, after)
            for sensor in _watcher.sensors.values():
                sensor.async_schedule_update_ha_state(False)

    # noinspection PyUnusedLocal
    @bot.event
    async def on_user_update(before: User, after: User):
        _watcher: DiscordAsyncMemberState = watchers.get("{}".format(after))
        if _watcher is not None:
            await update_discord_entity_user(_watcher, after)
            for sensor in _watcher.sensors.values():
                sensor.async_schedule_update_ha_state(False)

    # noinspection PyUnusedLocal
    @bot.event
    async def on_voice_state_update(_member: Member, before: VoiceState, after: VoiceState):
        _watcher = watchers.get("{}".format(_member))
        if _watcher is not None:
            if after.channel is not None:
                _watcher.voice_channel = after.channel.name
            else:
                _watcher.voice_channel = None
            _watcher.voice_deaf = after.deaf
            _watcher.voice_mute = after.mute
            _watcher.voice_self_deaf = after.self_deaf
            _watcher.voice_self_mute = after.self_mute
            _watcher.voice_self_stream = after.self_stream
            _watcher.voice_self_video = after.self_video
            _watcher.voice_afk = after.afk
            _watcher.async_schedule_update_ha_state(False)
            for sensor in _watcher.sensors.values():
                sensor.async_schedule_update_ha_state(False)

    @bot.event
    async def on_raw_reaction_add(payload: RawReactionActionEvent):
        channel_id = payload.channel_id
        _channel: GuildChannel = await bot.fetch_channel(channel_id)
        _member: Member = payload.member
        _chan = channels.get("{}".format(_channel))
        if _chan:
            _chan._state = _member.display_name
            _chan._last_user = _member.display_name
            _chan.async_schedule_update_ha_state(False)

    watchers = {}
    for member in config.get(CONF_MEMBERS):
        if re.match(r"^\d{,20}", str(member)):  # Up to 20 digits because 2^64 (snowflake-length) is 20 digits long
            user = await bot.fetch_user(member)
            if user:
                watcher: DiscordAsyncMemberState = \
                    DiscordAsyncMemberState(hass, bot, user.name, user.global_name, user.id)
                watchers[watcher.name] = watcher

    channels = {}
    for channel in config.get(CONF_CHANNELS):
        if re.match(r"^\d{,20}", str(channel)):  # Up to 20 digits because 2^64 (snowflake-length) is 20 digits long
            chan: GuildChannel = await bot.fetch_channel(channel)
            if chan:
                ch: DiscordAsyncReactionState = DiscordAsyncReactionState(hass, bot, chan.name, chan.id)
                channels[ch.name] = ch

    if len(watchers) > 0:
        async_add_entities(watchers.values())
        for sensors in watchers.values():
            async_add_entities(sensors.sensors.values())
        async_add_entities(channels.values())
        hass.bus.async_fire("discord_game_setup_finished")


class DiscordAsyncMemberState(SensorEntity):
    def __init__(self, hass, client, member, user_name, userid):
        self.member = member
        self.userid = userid
        self.hass = hass
        self.client = client
        self._state = 'unknown'
        self.activity_state = 'unknown'
        self.user_name = user_name
        self.display_name = None
        self.roles = None
        self.game = None
        self.game_state = None
        self.game_details = None
        self.game_image_small = None
        self.game_image_large = None
        self.game_image_small_text = None
        self.game_image_large_text = None
        self.game_image_capsule_231x87 = None
        self.game_image_capsule_467x181 = None
        self.game_image_capsule_616x353 = None
        self.game_image_header = None
        self.game_image_hero_capsule = None
        self.game_image_library_600x900 = None
        self.game_image_library_hero = None
        self.game_image_logo = None
        self.game_image_page_bg_raw = None
        self.streaming = None
        self.streaming_url = None
        self.streaming_details = None
        self.listening = None
        self.listening_url = None
        self.listening_details = None
        self.spotify_artists = None
        self.spotify_title = None
        self.spotify_album = None
        self.spotify_album_cover_url = None
        self.spotify_track_id = None
        self.spotify_duration = None
        self.spotify_start = None
        self.spotify_end = None
        self.watching = None
        self.watching_url = None
        self.watching_details = None
        self.avatar_url = None
        self.custom_status = None
        self.custom_emoji = None
        self.voice_channel = None
        self.voice_deaf = None
        self.voice_mute = None
        self.voice_self_deaf = None
        self.voice_self_mute = None
        self.voice_self_stream = None
        self.voice_self_video = None
        self.voice_afk = None
        self.entity_id = ENTITY_ID_FORMAT.format(self.userid)
        sensors_dict = {}
        for sensor_name in SENSORS:
            sensors_dict[sensor_name] = GenericSensor(sensor=self, attr=sensor_name)
        self.sensors = sensors_dict

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.member)},
            name=self.member
        )

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def native_value(self) -> str:
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return ENTITY_ID_FORMAT.format(self.userid)

    @property
    def name(self):
        return self.member

    @property
    def entity_picture(self):
        return self.avatar_url

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            'avatar_url': self.avatar_url,
            'activity_state': self.activity_state,
            'user_id': self.userid,
            'user_name': self.user_name,
            'display_name': self.display_name,
            'roles': self.roles,
            'game': self.game,
            'game_state': self.game_state,
            'game_details': self.game_details,
            'game_image_small': self.game_image_small,
            'game_image_large': self.game_image_large,
            'game_image_small_text': self.game_image_small_text,
            'game_image_large_text': self.game_image_large_text,
            'game_image_capsule_231x87': self.game_image_capsule_231x87,
            'game_image_capsule_467x181': self.game_image_capsule_467x181,
            'game_image_capsule_616x353': self.game_image_capsule_616x353,
            'game_image_header': self.game_image_header,
            'game_image_hero_capsule': self.game_image_hero_capsule,
            'game_image_library_600x900': self.game_image_library_600x900,
            'game_image_library_hero': self.game_image_library_hero,
            'game_image_logo': self.game_image_logo,
            'game_image_page_bg_raw': self.game_image_page_bg_raw,
            'streaming': self.streaming,
            'streaming_url': self.streaming_url,
            'streaming_details': self.streaming_details,
            'listening': self.listening,
            'listening_url': self.listening_url,
            'listening_details': self.listening_details,
            'spotify_artist': self.spotify_artists,
            'spotify_title': self.spotify_title,
            'spotify_album': self.spotify_album,
            'spotify_album_cover_url': self.spotify_album_cover_url,
            'spotify_track_id': self.spotify_track_id,
            'spotify_duration': self.spotify_duration,
            'spotify_start': self.spotify_start,
            'spotify_end': self.spotify_end,
            'watching': self.watching,
            'watching_url': self.watching_url,
            'watching_details': self.watching_details,
            'custom_status': self.custom_status,
            'custom_emoji': self.custom_emoji,
            'voice_channel': self.voice_channel,
            'voice_server_deafened': self.voice_deaf,
            'voice_server_muted': self.voice_mute,
            'voice_self_deafened': self.voice_self_deaf,
            'voice_self_muted': self.voice_self_mute,
            'voice_streaming': self.voice_self_stream,
            'voice_broadcasting_video': self.voice_self_video,
            'voice_afk': self.voice_afk
        }


class GenericSensor(SensorEntity):
    def __init__(self, sensor: DiscordAsyncMemberState, attr: str):
        self.sensor = sensor
        self.attr = attr
        self.entity_id = ENTITY_ID_FORMAT.format(self.sensor.userid) + "_" + self.attr

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def native_value(self) -> str:
        return getattr(self.sensor, self.attr)

    @property
    def unique_id(self):
        """Return a unique ID."""
        return ENTITY_ID_FORMAT.format(self.sensor.userid) + "_" + self.attr

    @property
    def name(self):
        return self.sensor.member + " " + self.attr

    @property
    def entity_picture(self):
        attr = getattr(self.sensor, self.attr)
        if validators.url(attr):
            return attr
        return None

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.sensor.member)},
            name=self.sensor.member
        )


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
    def native_value(self) -> str:
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return ENTITY_ID_CHANNEL_FORMAT.format(self._channel_id)

    @property
    def name(self):
        return self._channel_name

    @property
    def device_info(self) -> DeviceInfo:
        """Return the device info."""
        return DeviceInfo(
            identifiers={(DOMAIN, self.unique_id)},
            name=self._channel_name
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return {
            'last_user': self._last_user
        }
