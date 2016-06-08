class AbstractActor(object):
    config = None
    context = None
    running = True

    def init(self, config, context):
        pass

    def is_my_command(self, cmd, arg):
        return False

    def loop(self):
        pass

    def command(self, cmd, arg):
        pass

    def stop(self):
        self.running = False
