import logging
from typing import Optional, Dict, Any

import homeassistant.helpers.config_validation as cv
import nextcord
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers import selector
from nextcord import LoginFailure

from .const import DOMAIN, CONF_MEMBERS, CONF_CHANNELS, CONF_IMAGE_FORMAT, CONF_STEAM_API_KEY

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Required(CONF_IMAGE_FORMAT, default='webp'): selector.SelectSelector(
            selector.SelectSelectorConfig(options=['png', 'webp', 'jpeg', 'jpg'],
                                          multiple=False,
                                          mode=selector.SelectSelectorMode.DROPDOWN),
        ),
        vol.Optional(CONF_STEAM_API_KEY): selector.TextSelector(
            selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD),
        ),
    }
)


async def _validate_auth_and_fetch_data(token: str):
    """Authenticate with Discord and fetch guild members and channels.

    Returns (members_dict, user_names, channels_dict, channel_names).
    Raises ValueError on auth failure.
    """
    client = nextcord.Client(intents=nextcord.Intents.all())
    try:
        await client.login(token)
        guilds_iter = client.fetch_guilds()
        _LOGGER.debug("fetch_guilds() type: %s, value: %r", type(guilds_iter), guilds_iter)
        guilds = [g async for g in guilds_iter]
        _LOGGER.debug("guilds (as list): %s", guilds)

        members = {}
        channels = {}

        for guild in guilds:
            _members_iter = guild.fetch_members()
            _LOGGER.debug("fetch_members() type: %s, value: %r", type(_members_iter), _members_iter)
            _members = [m async for m in _members_iter]
            _LOGGER.debug("members (as list): %s", _members)
            for member in _members:
                members[member.name] = member

            _channels = await guild.fetch_channels()
            for channel in _channels:
                channels[channel.name] = channel
        _LOGGER.debug("members: %s", members)
        _LOGGER.debug("channels: %s", channels)

        user_names = list(members.keys())
        _LOGGER.debug("userNames: %s", user_names)

        channel_names = list(channels.keys())
        _LOGGER.debug("channelNames: %s", channel_names)

        return members, user_names, channels, channel_names
    except LoginFailure:
        raise ValueError("Invalid access token")
    finally:
        await client.close()


class DiscordGameConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    data: Optional[Dict[str, Any]]

    def __init__(self):
        self.members = {}
        self.user_names = []
        self.channels = {}
        self.channel_names = []

    @staticmethod
    def async_get_options_flow(_config_entry):
        return DiscordGameOptionsFlow()

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}
        if user_input is not None:
            try:
                self.members, self.user_names, self.channels, self.channel_names = \
                    await _validate_auth_and_fetch_data(user_input[CONF_ACCESS_TOKEN])
            except ValueError:
                errors["base"] = "auth"
            if not errors:
                self.data = user_input
                self.data[CONF_MEMBERS] = []
                self.data[CONF_CHANNELS] = []

                return await self.async_step_members()

        return self.async_show_form(
            step_id="user", data_schema=AUTH_SCHEMA, errors=errors
        )

    async def async_step_members(self, user_input: Optional[Dict[str, Any]] = None):
        _MEMBERS_SCHEMA = vol.Schema(
            {
                vol.Optional(CONF_MEMBERS): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=self.user_names,
                                                  multiple=True,
                                                  mode=selector.SelectSelectorMode.DROPDOWN),
                ),
                vol.Optional(CONF_CHANNELS): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=self.channel_names,
                                                  multiple=True,
                                                  mode=selector.SelectSelectorMode.DROPDOWN),
                ),
            }
        )

        errors: Dict[str, str] = {}
        if user_input is not None:
            for user in user_input.get(CONF_MEMBERS, []):
                self.data[CONF_MEMBERS].append(self.members.get(user).id)
            if user_input.get(CONF_CHANNELS):
                for channel in user_input.get(CONF_CHANNELS):
                    self.data[CONF_CHANNELS].append(self.channels.get(channel).id)

            return self.async_create_entry(title="Discord Game", data=self.data)

        return self.async_show_form(
            step_id="members", data_schema=_MEMBERS_SCHEMA, errors=errors
        )


class DiscordGameOptionsFlow(config_entries.OptionsFlow):
    def _get_current(self, key, default=None):
        """Get current value from options, falling back to data."""
        return self.config_entry.options.get(
            key, self.config_entry.data.get(key, default if default is not None else "")
        )

    async def async_step_init(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}
        if user_input is not None:
            try:
                self.members, self.user_names, self.channels, self.channel_names = \
                    await _validate_auth_and_fetch_data(user_input[CONF_ACCESS_TOKEN])
            except ValueError:
                errors["base"] = "auth"
            if not errors:
                self.options_data = user_input
                self.options_data[CONF_MEMBERS] = []
                self.options_data[CONF_CHANNELS] = []
                return await self.async_step_members()

        current_token = self._get_current(CONF_ACCESS_TOKEN)
        current_image_format = self._get_current(CONF_IMAGE_FORMAT, "webp")
        current_steam_key = self._get_current(CONF_STEAM_API_KEY)

        options_schema = vol.Schema(
            {
                vol.Required(CONF_ACCESS_TOKEN, default=current_token): cv.string,
                vol.Required(CONF_IMAGE_FORMAT, default=current_image_format): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=['png', 'webp', 'jpeg', 'jpg'],
                                                  multiple=False,
                                                  mode=selector.SelectSelectorMode.DROPDOWN),
                ),
                vol.Optional(CONF_STEAM_API_KEY, default=current_steam_key): selector.TextSelector(
                    selector.TextSelectorConfig(type=selector.TextSelectorType.PASSWORD),
                ),
            }
        )

        return self.async_show_form(step_id="init", data_schema=options_schema, errors=errors)

    async def async_step_members(self, user_input: Optional[Dict[str, Any]] = None):
        # Build a reverse lookup: ID -> name for pre-selecting current members/channels
        current_member_ids = set(self._get_current(CONF_MEMBERS, []))
        current_channel_ids = set(self._get_current(CONF_CHANNELS, []))

        preselected_members = [
            name for name, member in self.members.items()
            if member.id in current_member_ids
        ]
        preselected_channels = [
            name for name, channel in self.channels.items()
            if channel.id in current_channel_ids
        ]

        _MEMBERS_SCHEMA = vol.Schema(
            {
                vol.Optional(CONF_MEMBERS, default=preselected_members): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=self.user_names,
                                                  multiple=True,
                                                  mode=selector.SelectSelectorMode.DROPDOWN),
                ),
                vol.Optional(CONF_CHANNELS, default=preselected_channels): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=self.channel_names,
                                                  multiple=True,
                                                  mode=selector.SelectSelectorMode.DROPDOWN),
                ),
            }
        )

        errors: Dict[str, str] = {}
        if user_input is not None:
            for user in user_input.get(CONF_MEMBERS, []):
                member = self.members.get(user)
                if member:
                    self.options_data[CONF_MEMBERS].append(member.id)
            for channel in user_input.get(CONF_CHANNELS, []):
                ch = self.channels.get(channel)
                if ch:
                    self.options_data[CONF_CHANNELS].append(ch.id)

            return self.async_create_entry(title="", data=self.options_data)

        return self.async_show_form(
            step_id="members", data_schema=_MEMBERS_SCHEMA, errors=errors
        )
