"""Waste pick-up sensor for Oslo."""
import logging
from datetime import date, datetime
import async_timeout
import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.sensor import ENTITY_ID_FORMAT, PLATFORM_SCHEMA
from homeassistant.const import ATTR_FRIENDLY_NAME
from homeassistant.util import slugify
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity import Entity

REQUIREMENTS = ['beautifulsoup4==4.7.1'] # TODO: Remove this when it can be loaded with manifestfile

BASEURL = 'https://www.oslo.kommune.no/avfall-og-gjenvinning/avfallshenting/'

ATTR_PICKUP_DATE = 'pickup_date'
ATTR_PICKUP_FREQUENCY = 'pickup_frequency'
ATTR_ADDRESS = 'address'

_LOGGER = logging.getLogger(__name__)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required('address'): cv.string,
    vol.Optional('street'): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    ws = OsloWasteScraper(hass, config)
    await ws.async_update()
    waste_types = await ws.waste_types()

    for wt in waste_types:
        _LOGGER.info("Adding sensor for %s (%s)", config['address'], wt)
        async_add_entities([OsloWasteSensor(hass, ws, wt)], True)


class OsloWasteScraper:
    def __init__(self, hass, config):
        self.hass = hass
        self._address = config['address']
        self._street = config['street'] if 'street' in config else config['address']
        self._wastes = {}

    async def waste_types(self):
        return self._wastes.keys()

    async def async_update(self):
        from bs4 import BeautifulSoup  # TODO: Move this to the top when deps are installed from manifest
        with async_timeout.timeout(10, loop=self.hass.loop):
            req = await async_get_clientsession(
                self.hass).get(BASEURL, params={'street':self._street})
            result = await req.text()
        data = BeautifulSoup(result, 'html.parser')

        values = data.find('caption', text=self._address.upper())
        for v in values:
            root = v.parent.parent
            for w in root.select('tbody tr'):
                strings = w.select('td')
                self._wastes[strings[0].text] = {
                    'date': datetime.strptime(strings[1].text.split(' ')[1], '%d.%m.%Y').date(),
                    'frequency': strings[2].text}

    async def get_waste(self, waste):
        return self._wastes[waste]

class OsloWasteSensor(Entity):
    def __init__(self, hass, scraper, waste_type):
        self._state = None
        self._waste_type = waste_type
        self._scraper = scraper
        self._attributes = {
            ATTR_ADDRESS: self._scraper._address,
            ATTR_FRIENDLY_NAME: self._waste_type
            }
        self.entity_slug = "{} {}".format(self._scraper._address, self._waste_type)
        self.entity_id = ENTITY_ID_FORMAT.format(
            slugify(self.entity_slug.replace(' ', '_')))

    @property
    def unique_id(self):
        return self.entity_slug.replace(' ', '_')

    @property
    def name(self):
        return self._waste_type.title()

    @property
    def state(self):
        if self._state is not None:
            return (self._state - date.today()).days

    @property
    def device_state_attributes(self) -> dict:
        return self._attributes

    @property
    def unit_of_measurement(self):
        return 'days'

    @property
    def icon(self):
        """Return the icon."""
        return 'mdi:trash-can'

    async def async_update(self):
        """
        Ask scraper for new data if the current pickup date has passed or
        missing.
        """
        if self._state is not None:
            if (self._state - date.today()).days > 0:
                _LOGGER.info("%s - Skipping update.", self.entity_slug)
                return
        await self._scraper.async_update()

        pickup_date = await self._scraper.get_waste(self._waste_type)
        pickup_date = pickup_date.get('date')

        frequency = await self._scraper.get_waste(self._waste_type)
        frequency = frequency.get('frequency')

        self._attributes[ATTR_PICKUP_DATE] = pickup_date.isoformat()
        self._attributes[ATTR_PICKUP_FREQUENCY] = frequency
        self._attributes['attribution'] = "Data is provided by www.oslo.kommune.no"
        if pickup_date is not None:
            self._state = pickup_date
