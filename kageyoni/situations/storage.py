class MemorySituationStore:
    def __init__(self):
        self.data = {}

    def put(self, kind, key, value):
        self.data.setdefault(kind, {})[key] = value

    def get(self, kind, key):
        return self.data[kind][key]

    def contains(self, kind, key):
        return key in self.data.get(kind, {})

    def values(self, kind):
        return list(self.data.get(kind, {}).values())
