import os
from pathlib import Path

PROJECT_DIR = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_DIR / 'data'

print(f'{DATA_DIR}')

file_dir = os.getenv('DATA_DIR', str(DATA_DIR))
print(f'{DATA_DIR}')

