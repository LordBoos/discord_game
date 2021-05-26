import logging
import re

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from discord import ActivityType, Spotify, Game, Streaming, CustomActivity, Activity, Member, User, VoiceState
from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, EVENT_HOMEASSISTANT_START)

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['discord.py==1.5.1']

CONF_TOKEN = 'token'
CONF_MEMBERS = 'members'
CONF_IMAGE_FORMAT = 'image_format'

DOMAIN = 'sensor'

ENTITY_ID_FORMAT = "sensor.discord_user_{}"

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
        await bot.start(token)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_server)

    # noinspection PyUnusedLocal
    @bot.event
    async def on_error(error, *args, **kwargs):
        raise

    def update_discord_entity(watcher: DiscordAsyncMemberState, discord_member: Member):
        watcher._state = discord_member.status
        watcher._roles = [role.name for role in discord_member.roles]
        watcher._display_name = discord_member.display_name
        activity_state = None
        game = None
        game_state = None
        game_details = None
        game_image_small = None
        game_image_large = None
        game_image_small_text = None
        game_image_large_text = None
        streaming = None
        streaming_details = None
        streaming_url = None
        listening = None
        listening_details = None
        listening_url = None
        spotify_artists = None
        spotify_title = None
        spotify_album = None
        spotify_album_cover_url = None
        spotify_track_id = None
        spotify_duration = None
        spotify_start = None
        spotify_end = None
        watching = None
        watching_details = None
        watching_url = None
        custom_status = None
        custom_emoji = None
        voice_deaf = None
        voice_mute = None
        voice_self_deaf = None
        voice_self_mute = None
        voice_self_stream = None
        voice_self_video = None
        voice_afk = None
        voice_channel = None
        if discord_member.voice is not None:
            if discord_member.voice.channel is not None:
                voice_channel = discord_member.voice.channel.name
            else:
                voice_channel = None
            voice_deaf = discord_member.voice.deaf
            voice_mute = discord_member.voice.mute
            voice_self_deaf = discord_member.voice.self_deaf
            voice_self_mute = discord_member.voice.self_mute
            voice_self_stream = discord_member.voice.self_stream
            voice_self_video = discord_member.voice.self_video
            voice_afk = discord_member.voice.afk

        for activity in discord_member.activities:
            if activity.type == ActivityType.playing:
                if isinstance(activity, Game):
                    activity: Game
                    game = activity.name
                    continue
                else:
                    activity: Activity
                    game = activity.name
                    game_state = activity.state
                    game_details = activity.details
                    game_image_small = activity.small_image_url
                    game_image_large = activity.large_image_url
                    game_image_small_text = activity.small_image_text
                    game_image_large_text = activity.large_image_text
                    continue
            if activity.type == ActivityType.streaming:
                activity: Streaming
                streaming = activity.name
                streaming_details = activity.details
                streaming_url = activity.url
                continue
            if activity.type == ActivityType.listening:
                if isinstance(activity, Spotify):
                    activity: Spotify
                    listening = activity.title
                    spotify_artists = ", ".join(activity.artists)
                    spotify_title = activity.title
                    spotify_album = activity.album
                    spotify_album_cover_url = activity.album_cover_url
                    spotify_track_id = activity.track_id
                    spotify_duration = str(activity.duration)
                    spotify_start = str(activity.start)
                    spotify_end = str(activity.end)
                    continue
                else:
                    activity: Activity
                    activity_state = activity.state
                    listening = activity.name
                    listening_details = activity.details
                    listening_url = activity.url
                    continue
            if activity.type == ActivityType.watching:
                activity: Activity
                activity_state = activity.state
                watching = activity.name
                watching_details = activity.details
                watching_url = activity.url
                continue
            if activity.type == ActivityType.custom:
                activity: CustomActivity
                activity_state = activity.state
                custom_status = activity.name
                custom_emoji = activity.emoji.name if activity.emoji else None

        watcher._game = game
        watcher._game_state = game_state
        watcher._game_details = game_details
        watcher._game_image_small = game_image_small
        watcher._game_image_large = game_image_large
        watcher._game_image_small_text = game_image_small_text
        watcher._game_image_large_text = game_image_large_text
        watcher._streaming = streaming
        watcher._streaming_url = streaming_url
        watcher._streaming_details = streaming_details
        watcher._listening = listening
        watcher._listening_url = listening_url
        watcher._listening_details = listening_details
        watcher._spotify_artist = spotify_artists
        watcher._spotify_title = spotify_title
        watcher._spotify_album = spotify_album
        watcher._spotify_album_cover_url = spotify_album_cover_url
        watcher._spotify_track_id = spotify_track_id
        watcher._spotify_duration = spotify_duration
        watcher._spotify_start = spotify_start
        watcher._spotify_end = spotify_end
        watcher._watching = watching
        watcher._watching_url = watching_url
        watcher._watching_details = watching_details
        watcher._activity_state = activity_state
        watcher._custom_status = custom_status
        watcher._custom_emoji = custom_emoji
        watcher._voice_deaf = voice_deaf
        watcher._voice_mute = voice_mute
        watcher._voice_self_deaf = voice_self_deaf
        watcher._voice_self_mute = voice_self_mute
        watcher._voice_self_stream = voice_self_stream
        watcher._voice_self_video = voice_self_video
        watcher._voice_afk = voice_afk
        watcher._voice_channel = voice_channel
        watcher.async_schedule_update_ha_state(True)

    def update_discord_entity_user(watcher: DiscordAsyncMemberState, discord_user: User):
        watcher._avatar_url = discord_user.avatar_url_as(format=None, static_format=image_format, size=1024).__str__()
        watcher._userid = discord_user.id
        watcher._member = discord_user.name + '#' + discord_user.discriminator
        watcher._user_name = discord_user.name
        watcher.async_schedule_update_ha_state(True)

    @bot.event
    async def on_ready():
        users = {"{}".format(user): user for user in bot.users}
        members = {"{}".format(member): member for member in list(bot.get_all_members())}
        for name, watcher in watchers.items():
            if users.get(name) is not None:
                update_discord_entity_user(watcher, users.get(name))
            if members.get(name) is not None:
                update_discord_entity(watcher, members.get(name))

    # noinspection PyUnusedLocal
    @bot.event
    async def on_member_update(before: Member, after: Member):
        watcher = watchers.get("{}".format(after))
        if watcher is not None:
            update_discord_entity(watcher, after)

    # noinspection PyUnusedLocal
    @bot.event
    async def on_user_update(before: User, after: User):
        watcher: DiscordAsyncMemberState = watchers.get("{}".format(after))
        if watcher is not None:
            update_discord_entity_user(watcher, after)

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
            watcher.async_schedule_update_ha_state(True)

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
