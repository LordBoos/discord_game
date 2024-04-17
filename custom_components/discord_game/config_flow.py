import asyncio
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
        vol.Optional(CONF_IMAGE_FORMAT, default='webp'): selector.SelectSelector(
            selector.SelectSelectorConfig(options=['png', 'webp', 'jpeg', 'jpg'],
                                          multiple=False,
                                          mode=selector.SelectSelectorMode.DROPDOWN),
        ),
    }
)

client = nextcord.Client(intents=nextcord.Intents.all())
members = {}
userNames = []
channels = {}
channelNames = []


async def get_users(token: str):
    await client.start(token)
    global members
    members = {"{}".format(_member): _member for _member in list(client.get_all_members())}
    global channels
    channels = {"{}".format(_channel): _channel for _channel in list(client.get_all_channels())}


def task_callback(task: asyncio.Task):
    global userNames
    for key, val in members.items():
        userNames.append(val.name)
    global channelNames
    for key, val in channels.items():
        channelNames.append(val.name)


class DiscordGameConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    data: Optional[Dict[str, Any]]

    async def async_step_user(self, user_input: Optional[Dict[str, Any]] = None):
        errors: Dict[str, str] = {}
        if user_input is not None:
            try:
                await validate_auth(user_input[CONF_ACCESS_TOKEN])
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
        task = asyncio.create_task(get_users(token=self.data[CONF_ACCESS_TOKEN]))
        task.add_done_callback(task_callback)
        global client
        await client.wait_until_ready()
        await client.close()
        client = None
        client = nextcord.Client(intents=nextcord.Intents.all())
        _MEMBERS_SCHEMA = vol.Schema(
            {
                vol.Optional(CONF_MEMBERS): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=userNames,
                                                  multiple=True,
                                                  mode=selector.SelectSelectorMode.DROPDOWN),
                ),
            }
        )

        errors: Dict[str, str] = {}
        if user_input is not None:
            for user in user_input.get(CONF_MEMBERS):
                self.data[CONF_MEMBERS].append(members.get(user + '#0').id)

            return await self.async_step_channels()

        return self.async_show_form(
            step_id="members", data_schema=_MEMBERS_SCHEMA, errors=errors
        )

    async def async_step_channels(self, user_input: Optional[Dict[str, Any]] = None):
        task = asyncio.create_task(get_users(token=self.data[CONF_ACCESS_TOKEN]))
        task.add_done_callback(task_callback)
        global client
        await client.wait_until_ready()
        await client.close()
        client = None
        client = nextcord.Client(intents=nextcord.Intents.all())
        _CHANNELS_SCHEMA = vol.Schema(
            {
                vol.Optional(CONF_CHANNELS): selector.SelectSelector(
                    selector.SelectSelectorConfig(options=channelNames,
                                                  multiple=True,
                                                  mode=selector.SelectSelectorMode.DROPDOWN),
                ),
            }
        )

        errors: Dict[str, str] = {}
        if user_input is not None:
            for channel in user_input.get(CONF_CHANNELS):
                self.data[CONF_CHANNELS].append(channels.get(channel).id)

            return self.async_create_entry(title="Discord Game", data=self.data)

        return self.async_show_form(
            step_id="channels", data_schema=_CHANNELS_SCHEMA, errors=errors
        )


async def validate_auth(token: str) -> None:
    global client
    client = nextcord.Client(intents=nextcord.Intents.all())
    try:
        await client.login(token)
        await client.close()
        client = None
        client = nextcord.Client(intents=nextcord.Intents.all())
    except LoginFailure:
        raise ValueError
