import logging
import asyncio
import voluptuous as vol
import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
from homeassistant.const import (CONF_API_KEY, EVENT_HOMEASSISTANT_STOP, EVENT_HOMEASSISTANT_START )
from homeassistant.components.notify import (
    PLATFORM_SCHEMA, BaseNotificationService, ATTR_TARGET)
from homeassistant.util.async_ import run_callback_threadsafe

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
# https://raw.githubusercontent.com/Rapptz/discord.py/89eb3392afbb25df8a59e6bdd61531e90e48bbb8/docs/api.rst
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

    def update_discord_entity(discord_member, entity):
        if entity.name == "{}".format(discord_member):
            activity = None
            if discord_member.activity != None:
                activity = discord_member.activity.name
            attr = dict(entity.attributes)
            attr["game"] = activity
            hass.states.async_set(entity.entity_id, discord_member.status, attr)

    @bot.event
    async def on_ready():
        trackedMembers = (hass.states.get(entity_id) for entity_id in hass.states.async_entity_ids(DOMAIN))
        for entity in trackedMembers:
            for member in bot.get_all_members():
                update_discord_entity(member,entity)

    @bot.event
    async def on_member_update(before, after):
        trackedMembers = (hass.states.get(entity_id) for entity_id in hass.states.async_entity_ids(DOMAIN))
        for entity in trackedMembers:
            update_discord_entity(after, entity)

    watchers = []
    for member in config.get(CONF_MEMBERS):
        watcher = DiscordAsyncMemberState(hass, bot, member)
        watchers.append(watcher)
    if len(watchers) > 0:
        async_add_entities(watchers)
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

    @property
    def should_poll(self) -> bool:
        return False

    @property
    def state(self) -> str:
        return self._state

    @property
    def entity_id(self):
        """Return the entity ID."""
        return ENTITY_ID_FORMAT.format(self._member.replace("#","_")).lower()

    @property
    def name(self):
        return self._member

    @property
    def hidden(self):
        return True

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {'game': self._game}
