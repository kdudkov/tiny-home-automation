# tiny-home-automation
Small home automation system in Python, inspired by [OpenHAB](http://www.openhab.org/). It isn't production-ready, but works fine
on two my installations.

Works fine on Raspberry Pi. Works with sensors and actors via:
* MQTT broker (like Mosquitto) (and via [another my project](https://github.com/kdudkov/x10_mqtt) you can use X10 and Ubiquity mFi plugs)
* Modbus-TCP
* direct support of Kodi (XBMC) server
* direct support of [Kankun Wifi Plug](https://plus.google.com/communities/115308608951565782559)
* HTTP update from any other system
