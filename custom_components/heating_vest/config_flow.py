"""Configuration du gilet chauffant."""
from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import callback

from .const import CONF_ADDRESS, CONF_SERVICE, DEFAULT_SERVICE, DOMAIN


def _service_schema(default: str) -> dict:
    return {vol.Optional(CONF_SERVICE, default=default): str}


class VestConfigFlow(ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._discovery: BluetoothServiceInfoBleak | None = None

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return VestOptionsFlow()

    async def async_step_bluetooth(self, discovery_info: BluetoothServiceInfoBleak) -> ConfigFlowResult:
        await self.async_set_unique_id(discovery_info.address.upper())
        self._abort_if_unique_id_configured()
        self._discovery = discovery_info
        self.context["title_placeholders"] = {"name": discovery_info.address}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        assert self._discovery
        if user_input is not None:
            return self.async_create_entry(
                title="Gilet chauffant",
                data={
                    CONF_ADDRESS: self._discovery.address.upper(),
                    CONF_SERVICE: user_input.get(CONF_SERVICE, "").strip(),
                },
            )
        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(_service_schema(DEFAULT_SERVICE)),
            description_placeholders={"address": self._discovery.address},
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            address = user_input[CONF_ADDRESS].strip().upper()
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title="Gilet chauffant",
                data={CONF_ADDRESS: address, CONF_SERVICE: user_input.get(CONF_SERVICE, "").strip()},
            )
        found = [
            i.address
            for i in async_discovered_service_info(self.hass, connectable=False)
            if (i.name or "").lower().startswith("ves")
        ]
        default = found[0] if found else ""
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS, default=default): str, **_service_schema(DEFAULT_SERVICE)}
            ),
        )


class VestOptionsFlow(OptionsFlow):
    """Permet de changer l'action ESPHome utilisée pour émettre."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data={CONF_SERVICE: user_input.get(CONF_SERVICE, "").strip()})
        current = self.config_entry.options.get(
            CONF_SERVICE, self.config_entry.data.get(CONF_SERVICE, DEFAULT_SERVICE)
        )
        return self.async_show_form(step_id="init", data_schema=vol.Schema(_service_schema(current)))
