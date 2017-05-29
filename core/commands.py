def send_telegramm_kott(context, message):
    context.command('mqtt:telegram/Kott', message)


def send_telegramm_alenat(context, message):
    context.command('mqtt:telegram/Alena', message)


def all_lights_off(context, s):
    context.command('mqtt:x10/%s/command' % s, 'lightsoff')


def all_off(context, s):
    context.command('mqtt:x10/%s/command' % s, 'alloff')
