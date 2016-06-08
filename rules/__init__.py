from . import thermostat
from . import misc

rules = (
    thermostat.Thermostat('room_thermostat_switch', 'room_temp_pi', 'room_thermostat', 'kankun_switch', False),
    misc.PressureRule(),
)
