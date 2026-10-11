import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = Path(os.getenv('BMWPM_DATA_DIR', str(ROOT / '.local'))).resolve()
DB_URL = os.getenv('BMWPM_DATABASE_URL', f"sqlite:///{(DATA_DIR / 'cockpit.sqlite').as_posix()}")
PIPELINE_VERSION = 'evidence-v1.0'
MAPPING_VERSION = 'taxonomy-v2-tags-1.0'
RANKING_VERSION = 'demand-v1.0'
PROMPT_VERSION = 'requirements-v1.1'
SCHEMA_VERSION = 'analysis-v1.0'
DEFAULT_MODEL = 'gpt-4.1-mini-2025-04-14'

def ensure_directories():
    for folder in ('sources', 'exports', 'replays', 'evaluation', 'previews'):
        (DATA_DIR / folder).mkdir(parents=True, exist_ok=True)
