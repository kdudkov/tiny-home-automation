def time_minutes(t):
    if t is None:
        return '0 м'
    res = ''
    n = t
    h = int(n / 3600)
    if h:
        res = '%d ч' % h
    n %= 3600
    m = int(n / 60)
    res += '%d м' % m
    return res.strip()
