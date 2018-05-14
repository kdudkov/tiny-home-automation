# coding: UTF-8


def time_minutes(t):
    if t is None:
        return '0м'
    res = ''
    n = t
    h = int(n / 3600)
    if h:
        res = '%dч' % h
    n %= 3600
    m = int(n / 60)
    res += ' %dм' % m
    return res.strip()
