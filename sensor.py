import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import Entity, generate_entity_id
from homeassistant.components.sensor import PLATFORM_SCHEMA, ENTITY_ID_FORMAT
from homeassistant.const import ATTR_FRIENDLY_NAME

import voluptuous as vol
from datetime import datetime, date
import requests

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required('address'): cv.string,
    vol.Optional('street'): cv.string,
})

REQUIREMENTS = ['beautifulsoup4==4.7.1']
BASEURL = 'https://www.oslo.kommune.no/avfall-og-gjenvinning/nar-hentes-avfallet/'

ATTR_PICKUP_DATE = 'pickup_date'
ATTR_PICKUP_FREQUENCY = 'pickup_frequency'
ATTR_ADDRESS = 'address'

def setup_platform(hass, config, add_devices, discovery_info=None):
    ws = OsloWasteScraper(config)

    for wt in ws.waste_types():
        add_devices([OsloWasteSensor(hass, ws, wt)], True)


class OsloWasteScraper:
    def __init__(self, config):
        self._address = config['address']
        self._street = config['street'] if 'street' in config else config['address']
        self._wastes = {}
        self.update()

    def waste_types(self):
        return self._wastes.keys()

    def update(self):
        from bs4 import BeautifulSoup
        req = requests.get(BASEURL, timeout=10, params={'street':self._street})
        data = BeautifulSoup(req.text, 'html.parser')
        
        values = data.find('caption', text=self._address.upper())
        for v in values:
            root = v.parent.parent
            caption = root.find('caption').text
            for w in root.select('tbody tr'):
                strings = w.select('td')
                self._wastes[strings[0].text] = {
                    'date': datetime.strptime(strings[1].text.split(' ')[1],'%d.%m.%Y').date(),
                    'frequency': strings[2].text }

    def get_waste(self, waste):
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
        self.entity_id = generate_entity_id(
            ENTITY_ID_FORMAT, self._scraper._address + ' ' + self._waste_type, hass=hass)

    @property
    def name(self):
        return self._waste_type

    @property
    def state(self):
        if self._state == None:
            return self._state
        return (self._state - date.today()).days

    @property
    def device_state_attributes(self) -> dict:
        return self._attributes

    @property
    def unit_of_measurement(self):
        return 'days'

    def update(self):
        # Ask scraper for new data if the current pickup date has passed or
        # missing.
        if self._state == None or (self._state - date.today()).days < 0:
            self._scraper.update()
        self._state = self._scraper.get_waste(self._waste_type)['date']
        self._attributes[ATTR_PICKUP_DATE] = self._state.isoformat()
        self._attributes[ATTR_PICKUP_FREQUENCY] = self._scraper.get_waste(self._waste_type)['frequency']
