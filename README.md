# Oslo Kommune, Avfall og gjenvinning

This sensor queries the web pages of Oslo Kommune for information about when garbage will be picked up.  It provides one sensor for each class of garbage, with their state set to the amount of days left until the garbage will be picked up.


### Installation

Clone this folder to `<config_dir>/custom_components/oslo_waste/`.

Add the following to your `configuration.yaml` file:

```yaml
# Example configuration.yaml entry
sensor:
  - platform: oslo_waste
    address: 'Drammensveien 1'
```

The address entry is mandatory, and should match with one of the headings in the search results after searching on this web page: https://www.oslo.kommune.no/avfall-og-gjenvinning/avfallshenting/.  If searching for your address does not return the search results you need, you can set the search string with the optional 'street' config option.
