import os
from pathlib import Path

CONFIG_DIR = Path(__file__).resolve().parent / 'config'

os.makedirs(CONFIG_DIR, exist_ok=True)