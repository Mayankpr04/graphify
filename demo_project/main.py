import utilities
from utilities import Cache
from helpers import format_output, validate


def run(path):
    config = utilities.load_config(path)
    cache = Cache()
    cache.set("config", config)
    raw = "  hello  "
    data = utilities.parse_data(raw)
    if validate(data):
        print(format_output(data))


def main():
    run("config.yaml")
