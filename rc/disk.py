class Disk:
    def __init__(self, name, *, provider, size, type):
        self.name = name
        self.provider = provider
        self.size = size
        self.type = type
