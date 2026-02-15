class BotState:
    def __init__(self):
        self.drivers = {}        # {profile_num: driver}
        self.stop_all = False
        self.paused = False
        self.setup_index = 0

    def reset(self):
        self.stop_all = False
        self.paused = False
        self.setup_index = 0
