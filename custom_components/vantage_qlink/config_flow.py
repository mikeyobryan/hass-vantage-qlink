"""Config flow for Vantage QLink integration."""

from __future__ import annotations

import logging
from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError

from .command_client.commands import CommandClient
from .const import CONF_LIGHTS, CONF_COVERS, DOMAIN

_LOGGER = logging.getLogger(__name__)


STEP_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Required(CONF_PORT, description="Port", default=3040): int,
        vol.Optional(CONF_LIGHTS, default="", description="Lights"): str,
        vol.Optional(CONF_COVERS, default="", description="Covers"): str,
    }
)


async def validate_connection(host, port):
    """Validate we can connect to the QLink system."""
    async with CommandClient(host, port, conn_timeout=5) as client:
        await client.command("VGV")


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect.

    Data has the keys from STEP_DATA_SCHEMA with values provided by the user.
    """
    try:
        await validate_connection(data[CONF_HOST], data[CONF_PORT])
    except Exception as err:
        _LOGGER.error("Failed to connect to Vantage QLink: %s", err)
        raise CannotConnect from err


class ConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Vantage QLink."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors = {}
        if user_input is not None:
            try:
                await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

            if not errors:
                # Use .get() with defaults so Optional fields never cause KeyError
                lights = user_input.get(CONF_LIGHTS, "")
                covers = user_input.get(CONF_COVERS, "")

                return self.async_create_entry(
                    title=f"Vantage QLink {user_input[CONF_HOST]}",
                    data={
                        CONF_HOST: user_input[CONF_HOST],
                        CONF_PORT: user_input[CONF_PORT],
                    },
                    options={
                        CONF_LIGHTS: lights,
                        CONF_COVERS: covers,
                    },
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return OptionsFlowHandler(config_entry)


class OptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        errors = {}
        if user_input is not None:
            lights = user_input.get(CONF_LIGHTS, "")
            covers = user_input.get(CONF_COVERS, "")

            return self.async_create_entry(
                title="",
                data={
                    CONF_LIGHTS: lights,
                    CONF_COVERS: covers,
                },
            )

        # Pre-fill the form with the existing options
        options = self.config_entry.options
        lights = options.get(CONF_LIGHTS, "")
        covers = options.get(CONF_COVERS, "")

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_LIGHTS, default=lights, description="Lights"
                    ): str,
                    vol.Optional(
                        CONF_COVERS, default=covers, description="Covers"
                    ): str,
                }
            ),
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
