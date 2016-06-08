def send_telegramm_kott(context, message):
    context.command('mqtt:telegram/Kott', message)


def send_telegramm_alenat(context, message):
    context.command('mqtt:telegram/Alena', message)
