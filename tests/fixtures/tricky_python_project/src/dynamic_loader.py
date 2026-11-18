"""Dynamic module loader."""
import importlib

def fetch_external_url(url: str):
    # Dynamic import via importlib.import_module
    requests_mod = importlib.import_module("requests")
    return requests_mod.get(url)
