from .abstract import Rule


class ConvertPressureRule(Rule):
    on_change = ['pressure_mm']

    def process(self, name, val, old_val, age):
        if val:
            val1 = val * 1.33322
            self.post_update('pressure', val1)
