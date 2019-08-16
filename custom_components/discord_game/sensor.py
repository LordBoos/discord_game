import asyncio
import logging

import homeassistant.helpers.config_validation as cv
import voluptuous as vol
from homeassistant.components.notify import PLATFORM_SCHEMA
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, EVENT_HOMEASSISTANT_START)
from homeassistant.helpers.entity import Entity

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['https://github.com/Rapptz/discord.py/archive/03fdd8153116fe2df16a7227cea731cbfeabf9ec.zip#discord.py[voice]']

CONF_TOKEN = 'token'
CONF_MEMBERS = 'members'

DOMAIN = 'sensor'

ENTITY_ID_FORMAT = "sensor.discord_{}"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_TOKEN): cv.string,
    vol.Required(CONF_MEMBERS, default=[]): vol.All(cv.ensure_list, [cv.string]),
})


@asyncio.coroutine
def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    import discord
    token = config.get(CONF_TOKEN)
    bot = discord.Client(loop=hass.loop)
    yield from bot.login(token)

    @asyncio.coroutine
    def async_stop_server(event):
        yield from bot.logout()

    @asyncio.coroutine
    def start_server(event):
        hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STOP, async_stop_server)
        yield from bot.start(token)

    hass.bus.async_listen_once(EVENT_HOMEASSISTANT_START, start_server)

    @bot.event
    async def on_error(error, *args, **kwargs):
        raise

    def update_discord_entity(watcher, discord_member):
        activity = None
        if discord_member.activity is not None:
            activity = discord_member.activity.name
        watcher._state = discord_member.status
        watcher._game = activity
        watcher.async_schedule_update_ha_state()

    def update_discord_entity_user(watcher, discord_user):
        watcher._avatar_id = discord_user.avatar
        watcher._user_id = discord_user.id
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

    @bot.event
    async def on_member_update(before, after):
        watcher = watchers.get("{}".format(after))
        if watcher is not None:
            update_discord_entity(watcher, after)

    @bot.event
    async def on_user_update(before, after):
        watcher = watchers.get("{}".format(after))
        if watcher is not None:
            update_discord_entity_user(watcher, after)

    watchers = {}
    for member in config.get(CONF_MEMBERS):
        watcher = DiscordAsyncMemberState(hass, bot, member)
        watchers[watcher.name] = watcher
    if len(watchers) > 0:
        async_add_entities(watchers.values())
        return True
    else:
        return False


class DiscordAsyncMemberState(Entity):
    def __init__(self, hass, client, member):
        self._member = member
        self._hass = hass
        self._client = client
        self._state = 'unknown'
        self._game = None
        self._avatar_url = None
        self._avatar_id = None
        self._user_id = None

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def state(self) -> str:
        return self._state

    @property
    def entity_id(self):
        """Return the entity ID."""
        return ENTITY_ID_FORMAT.format(self._member.replace("#", "_")).lower()

    @property
    def name(self):
        return self._member

    @property
    def entity_picture(self):
        return self._avatar_url

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {'game': self._game}

    def update(self):
        if self._user_id is not None and self._avatar_id is not None:
            self._avatar_url = 'https://cdn.discordapp.com/avatars/' + str(self._user_id) + '/' + str(self._avatar_id) + '.webp?size=1024'
