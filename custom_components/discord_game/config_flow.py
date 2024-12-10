import logging
from typing import Optional, Dict, Any

import homeassistant.helpers.config_validation as cv
import nextcord
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_ACCESS_TOKEN
from homeassistant.helpers import selector
from nextcord import LoginFailure

from .const import DOMAIN, CONF_MEMBERS, CONF_CHANNELS, CONF_IMAGE_FORMAT

_LOGGER = logging.getLogger(__name__)

AUTH_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ACCESS_TOKEN): cv.string,
        vol.Required(CONF_IMAGE_FORMAT, default='webp'): selector.SelectSelector(
            selector.SelectSelectorConfig(options=['png', 'webp', 'jpeg', 'jpg'],
                                          multiple=False,
                                          mode=selector.SelectSelectorMode.DROPDOWN),
        ),
    }
)


class DiscordGameConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    data: Optional[Dict[str, Any]]

    def __init__(self):
        self.members = {}
        self.user_names = []
        self.channels = {}
        self.channel_names = []

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}
        if user_input is not None:
            try:
                await self.validate_auth_and_fetch_data(user_input[CONF_ACCESS_TOKEN])
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

    async def validate_auth_and_fetch_data(self, token: str) -> None:
        """Authenticate with Discord and fetch guild data."""
        client = nextcord.Client(intents=nextcord.Intents.all())
        try:
            await client.login(token)
            guilds = await client.fetch_guilds().flatten()
            _LOGGER.debug("guilds: %s", guilds)

            self.members = {}
            self.channels = {}

            for guild in guilds:
                _members = await guild.fetch_members().flatten()
                for member in _members:
                    self.members[member.name] = member

                _channels = await guild.fetch_channels()
                for channel in _channels:
                    self.channels[channel.name] = channel
            _LOGGER.debug("members: %s", self.members)
            _LOGGER.debug("channels: %s", self.channels)

            self.user_names = list(self.members.keys())
            _LOGGER.debug("userNames: %s", self.user_names)

            self.channel_names = list(self.channels.keys())
            _LOGGER.debug("channelNames: %s", channelNames)
        except LoginFailure:
            raise ValueError("Invalid access token")
        finally:
            await client.close()
