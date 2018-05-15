# tiny-home-automation
Small home automation system in Python, inspired by [OpenHAB](http://www.openhab.org/) and  [Home Assistant](https://www.home-assistant.io/)
. It isn't production-ready, but works fine on two my installations.

Works fine on Raspberry Pi. Works with sensors and actors via:
* MQTT broker (like Mosquitto) (and via [another my project](https://github.com/kdudkov/x10_mqtt) you can use X10 and Ubiquity mFi plugs)
* Modbus-TCP
* direct support of Kodi (XBMC) server
* direct support of [Kankun Wifi Plug](https://plus.google.com/communities/115308608951565782559)
* HTTP update from any other system

Now uses yml-based rules.

Example of rule turning on backlight (sonoff s20 module) on pir sensor is active on esp8266 and turning it off 30 seconds
after pir is inactive, doing this night-time only and if main light is off:

```yml
- name: 'night_light_on'
  trigger:
    items:
    - item_id: room_pir
      to: 'On'
  condition:
    condition_type: and
    conditions:
    - condition_type: state
      item_id: light_room
      state: 'Off'
    - condition_type: state
      item_id: home_mode
      state: 'night'
  action:
  - service: command
    item_id: s20_2
    value: 'On'

- name: 'night_light_off'
  trigger:
    items:
    - item_id: room_pir
      to: 'Off'
      for:
        seconds: 30
  condition:
    condition_type: and
    conditions:
    - condition_type: state
      item_id: light_room
      state: 'Off'
    - condition_type: state
      item_id: home_mode
      state: 'night'
  action:
  - service: command
    item_id: s20_2
    value: 'Off'
```