from datetime import datetime

name = '*cron*'


def check_cron_value(val, dt):
    a = []
    if isinstance(val, (dict, list)):
        a = list(val)
    if isinstance(val, str):
        a = val.split()

    if isinstance(dt, (int, float)):
        dt = datetime.fromtimestamp(dt)

    for c, v in zip(a, (dt.minute, dt.hour, dt.day, dt.month, dt.isoweekday())):
        if not test_val(c, v):
            return False

    return True


def test_val(c, v):
    if c == '*':
        return True

    values = get_values(c)

    for val in values:
        if '/' in str(val):
            _, n = val.split('/')
            if int(v) % int(n) == 0:
                return True
        else:
            if int(v) == int(val):
                return True
    return False


def get_values(v):
    res = []

    if ',' in v:
        parsed = [x.strip() for x in v.split(',') if x.strip()]
    else:
        parsed = [v.strip(), ]

    for s in parsed:
        if '-' in s:
            a, b = [int(x) for x in s.split('-', 1)]
            res += range(a, b + 1)
        else:
            res.append(s)

    return res
