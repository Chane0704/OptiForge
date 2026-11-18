"""Main application entry point."""
import os
from dotenv import load_dotenv
from google import genai
import yaml
from PIL import Image

load_dotenv()

def initialize():
    client = genai.Client()
    return client

def process_data():
    with open("config.yaml", "r") as f:
        config = yaml.safe_load(f)
    img = Image.new("RGB", (100, 100))
    return config, img
