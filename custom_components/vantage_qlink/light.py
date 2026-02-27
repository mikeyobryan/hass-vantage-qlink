import math

from homeassistant.components.light import ATTR_BRIGHTNESS, ColorMode, LightEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import (
    DeviceInfo,
    async_entries_for_config_entry,
    async_get as get_device_registry,
)
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)

from .command_client.commands import CommandClient
from .command_client.load import LoadInterface
from .const import CONF_LIGHTS, DOMAIN

BRIGHTNESS_SCALE = (1, 255)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the light platform."""

    client: CommandClient = hass.data[DOMAIN][entry.entry_id]

    # Safely get the lights list — handle None, empty string, whitespace
    raw_lights = entry.options.get(CONF_LIGHTS, "")
    current_device_ids = (
        [item.strip() for item in raw_lights.split(",") if item.strip()]
        if raw_lights
        else []
    )

    async_add_entities(
        QLinkLight(contractor_number=deviceId, client=client)
        for deviceId in current_device_ids
    )

    # Remove devices no longer present
    await remove_unlisted_devices(hass, entry, current_device_ids=current_device_ids)


async def remove_unlisted_devices(
    hass: HomeAssistant, entry: ConfigEntry, current_device_ids: list[str]
):
    registered_devices = async_entries_for_config_entry(
        get_device_registry(hass), entry.entry_id
    )
    device_registry = get_device_registry(hass)

    for device in registered_devices:
        # Assuming the identifiers tuple contains your service's unique ID
        device_unique_id = next(iter(device.identifiers))[1]
        if (
            device_unique_id.startswith("vantage_light_")
            and device_unique_id.replace("vantage_light_", "")
            not in current_device_ids
        ):
            device_registry.async_remove_device(device.id)


class QLinkLight(LightEntity):
    _level: int = 0

    def __init__(self, contractor_number: int | str, client: CommandClient) -> None:
        super().__init__()
        cn = str(contractor_number).strip()
        self._contractor_number = int(cn) if cn.isdigit() else cn
        self._client = LoadInterface(client)

    async def async_update(self):
        try:
            self._level = await self._client.get_level(self._contractor_number)
        except Exception:
            # If we can't reach the device, don't crash — just keep last level
            pass

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={
                (DOMAIN, f"{self._contractor_number}"),
            },
            name=f"Load {self._contractor_number}",
            manufacturer="Vantage",
            model="QLink Load",
            serial_number=f"{self._contractor_number}",
        )

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"vantage_light_{self._contractor_number}"

    @property
    def is_on(self) -> bool | None:
        """Return whether the light is on."""
        return self._level > 0

    @property
    def brightness(self) -> int | None:
        """Return the brightness of this light between 0..255."""
        return math.ceil(percentage_to_ranged_value(BRIGHTNESS_SCALE, self._level))

    @property
    def color_mode(self) -> ColorMode:
        """Return the color mode of the light."""
        return ColorMode.BRIGHTNESS

    @property
    def should_poll(self) -> bool:
        return True

    @property
    def supported_color_modes(self) -> set[ColorMode] | None:
        """Flag supported color modes."""
        return {ColorMode.BRIGHTNESS}

    async def async_turn_on(self, **kwargs) -> None:
        """Instruct the light to turn on."""
        self._level = ranged_value_to_percentage(
            BRIGHTNESS_SCALE, kwargs.get(ATTR_BRIGHTNESS, 255)
        )
        await self._client.set_level(self._contractor_number, self._level)

    async def async_turn_off(self, **kwargs) -> None:
        """Instruct the light to turn off."""
        self._level = 0
        await self._client.set_level(self._contractor_number, self._level)
