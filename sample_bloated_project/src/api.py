"""Sample API module with both active and dead code."""

import click
import requests
import time

def fetch_data(url: str):
    """Active function that fetches external data."""
    click.echo(f"Fetching from {url}...")
    resp = requests.get(url, timeout=5)
    return resp.json()

async def handle_request_async(item_id: int):
    """Async endpoint with blocking call that freezes event loop."""
    time.sleep(0.5)
    return {"status": "ok", "id": item_id}

def _unused_legacy_calculation(a: int, b: int) -> int:
    """Dead internal helper that is never called."""
    intermediate = a * 100
    return intermediate + b
