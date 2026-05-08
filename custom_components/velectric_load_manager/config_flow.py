"""Config flow for VElectric Load Manager integration."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import re
from typing import Any

import voluptuous as vol
import websockets

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import (
    CONF_HOST,
    CONF_PORT,
    CONF_NAME,
    CONF_VOLTAGE,
    CONF_SCAN_INTERVAL,
    DEFAULT_PORT,
    DEFAULT_VOLTAGE,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
)


_LOGGER = logging.getLogger(__name__)


STEP_USER_DATA_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_HOST): str,
        vol.Optional(CONF_PORT, default=DEFAULT_PORT): vol.All(
            int, vol.Range(min=1, max=65535)
        ),
        vol.Optional(CONF_NAME): str,
        vol.Optional(CONF_VOLTAGE, default=DEFAULT_VOLTAGE): vol.All(
            vol.Coerce(float), vol.Range(min=100, max=400)
        ),
        vol.Optional(CONF_SCAN_INTERVAL, default=DEFAULT_SCAN_INTERVAL): vol.All(
            vol.Coerce(int), vol.Range(min=1, max=60)
        ),
    }
)


def _validate_hostname(hostname: str) -> None:
    """Validate hostname or IP address."""
    hostname = hostname.strip()

    # Check for invalid characters
    if any(char in hostname for char in ["<", ">", '"', "'"]):
        raise CannotConnect("Invalid characters in hostname")

    try:
        # Try to parse as IP address
        ipaddress.ip_address(hostname)
        return  # Valid IP address
    except ValueError:
        # Check if it's a valid hostname
        if len(hostname) > 253:
            raise CannotConnect("Hostname too long")

        hostname = hostname.rstrip(".")
        allowed = re.compile(r"^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?$")
        if not all(allowed.match(x) for x in hostname.split(".")):
            raise CannotConnect("Invalid hostname format")


async def validate_input(hass: HomeAssistant, data: dict[str, Any]) -> dict[str, Any]:
    """Validate the user input allows us to connect."""
    host = data[CONF_HOST].strip()
    port = data[CONF_PORT]

    # Validate hostname/IP format
    _validate_hostname(host)

    # Test websocket connection
    ws_url = f"ws://{host}:{port}/ws"
    try:
        # Simple connection test with timeout
        async with asyncio.timeout(5):
            websocket = await websockets.connect(ws_url)
            await websocket.close()
    except asyncio.TimeoutError:
        _LOGGER.error("Connection to VElectric device timed out")
        raise CannotConnect("Connection timeout")
    except Exception as err:
        _LOGGER.error("Failed to connect to VElectric device: %s", err)
        raise CannotConnect("Connection failed")

    # Return info to store in the config entry
    device_name = data.get(CONF_NAME)
    if not device_name:
        device_name = f"VElectric Load Manager ({host})"
    return {"title": device_name}


class ConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for VElectric Load Manager."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle the initial step."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                info = await validate_input(self.hass, user_input)
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"
            else:
                return self.async_create_entry(title=info["title"], data=user_input)

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_DATA_SCHEMA, errors=errors
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        """Get the options flow for this handler."""
        return OptionsFlow()


class OptionsFlow(config_entries.OptionsFlow):
    """Handle options flow for VElectric Load Manager."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        errors: dict[str, str] = {}

        if user_input is not None:
            try:
                # Validate connection if host or port changed
                host_changed = (
                    user_input.get(CONF_HOST) != self.config_entry.data[CONF_HOST]
                )
                port_changed = user_input.get(CONF_PORT) != self.config_entry.data.get(
                    CONF_PORT, DEFAULT_PORT
                )

                if host_changed or port_changed:
                    # Test new connection before updating
                    test_data = {
                        CONF_HOST: user_input.get(
                            CONF_HOST, self.config_entry.data[CONF_HOST]
                        ),
                        CONF_PORT: user_input.get(
                            CONF_PORT,
                            self.config_entry.data.get(CONF_PORT, DEFAULT_PORT),
                        ),
                    }
                    await validate_input(self.hass, test_data)

                # Update the config entry data with all configurable fields
                new_data = {
                    **self.config_entry.data,
                    CONF_HOST: user_input.get(
                        CONF_HOST, self.config_entry.data[CONF_HOST]
                    ),
                    CONF_PORT: user_input.get(
                        CONF_PORT, self.config_entry.data.get(CONF_PORT, DEFAULT_PORT)
                    ),
                    CONF_NAME: user_input.get(
                        CONF_NAME, self.config_entry.data.get(CONF_NAME)
                    ),
                    CONF_VOLTAGE: user_input.get(
                        CONF_VOLTAGE,
                        self.config_entry.data.get(CONF_VOLTAGE, DEFAULT_VOLTAGE),
                    ),
                    CONF_SCAN_INTERVAL: user_input.get(
                        CONF_SCAN_INTERVAL,
                        self.config_entry.data.get(
                            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
                        ),
                    ),
                }

                # Update the config entry with new data
                self.hass.config_entries.async_update_entry(
                    self.config_entry, data=new_data
                )

                # Update coordinator directly instead of reloading to preserve energy sensor state
                if host_changed or port_changed:
                    coordinator = self.hass.data[DOMAIN][self.config_entry.entry_id]
                    await coordinator.async_update_config(
                        new_data[CONF_HOST],
                        new_data.get(CONF_PORT, DEFAULT_PORT),
                        new_data.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL),
                    )

                return self.async_create_entry(title="", data={})
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        # Pre-fill current values
        current_host = self.config_entry.data[CONF_HOST]
        current_port = self.config_entry.data.get(CONF_PORT, DEFAULT_PORT)
        current_name = self.config_entry.data.get(
            CONF_NAME, f"VElectric Load Manager ({current_host})"
        )
        current_voltage = self.config_entry.data.get(CONF_VOLTAGE, DEFAULT_VOLTAGE)
        current_scan_interval = self.config_entry.data.get(
            CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL
        )

        options_schema = vol.Schema(
            {
                vol.Required(CONF_HOST, default=current_host): str,
                vol.Optional(CONF_PORT, default=current_port): vol.All(
                    int, vol.Range(min=1, max=65535)
                ),
                vol.Optional(CONF_NAME, default=current_name): str,
                vol.Optional(CONF_VOLTAGE, default=current_voltage): vol.All(
                    vol.Coerce(float), vol.Range(min=100, max=400)
                ),
                vol.Optional(
                    CONF_SCAN_INTERVAL, default=current_scan_interval
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
            }
        )

        return self.async_show_form(
            step_id="init",
            data_schema=options_schema,
            errors=errors,
        )


class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""
