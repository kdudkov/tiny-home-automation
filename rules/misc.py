from .abstract import Rule

class PressureRule(Rule):
    on_change = ['pressure_mm']

    def process(self, name, old_val, val):
        if val:
            val1 = val * 1.33322
            self.post_update('pressure', val1)
