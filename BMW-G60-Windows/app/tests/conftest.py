"""Integration checks use a disposable SQLite backup, never the reviewer's database."""
import os
import sqlite3
import uuid
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]
SEED=Path(os.getenv('BMWPM_TEST_SEED',str(ROOT/'.local'/'cockpit.sqlite'))).resolve()
TEST_DIR=ROOT/'.local'/'test-runs'/uuid.uuid4().hex
TEST_DIR.mkdir(parents=True,exist_ok=True)
os.environ['BMWPM_DATA_DIR']=str(TEST_DIR)
os.environ['BMWPM_DATABASE_URL']='sqlite:///'+(TEST_DIR/'cockpit.sqlite').as_posix()

from backend.db import engine,SessionLocal

@pytest.fixture(autouse=True)
def isolated_database():
    if not SEED.exists():pytest.fail('Import the supplied archive before running the integration suite. See README.md.')
    engine.dispose()
    with sqlite3.connect(f'file:{SEED.as_posix()}?mode=ro',uri=True) as source,sqlite3.connect(TEST_DIR/'cockpit.sqlite') as target:
        source.backup(target)
    yield
    engine.dispose()

@pytest.fixture
def session():
    with SessionLocal() as s:yield s

@pytest.fixture
def client():
    from backend.app import app
    from fastapi.testclient import TestClient
    with TestClient(app) as c:yield c
