from .abstract import Rule


class HomeMode(Rule):
    on_change = ['home_mode']
    thermostats = ['room_thermostat']

    def process(self, name, val, old_val, age):
        if val in ('day', 'waiting'):
            for s in self.thermostats:
                self.post_update(s, 19)

        if val == 'night':
            for s in self.thermostats:
                self.post_update(s, 17)

        if val == 'nobody_home':
            for s in self.thermostats:
                self.post_update(s, 5)
