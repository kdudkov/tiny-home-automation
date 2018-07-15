class AbstractActor(object):
    config = None
    context = None
    running = True
    name = None

    def init(self, config, context):
        pass

    def loop(self):
        pass

    def command(self, args):
        pass

    def stop(self):
        self.running = False

    def format_simple_cmd(self, d, cmd):
        return cmd
