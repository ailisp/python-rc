from timeit import default_timer as timer
from humanfriendly import format_timespan


class Timer():
    def __init__(self, action):
        self.action = action

    def __enter__(self):
        self.start = timer()

    def __exit__(self, type, value, traceback):
        print("Time to", self.action+":", format_timespan(timer()-self.start))
