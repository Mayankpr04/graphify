def load_config(path):
    return {"path": path}


def parse_data(raw):
    return raw.strip()


class Cache:
    def __init__(self):
        self.store = {}

    def get(self, key):
        return self.store.get(key)

    def set(self, key, value):
        self.store[key] = value
