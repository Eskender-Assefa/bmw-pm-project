"""Assemble a relocatable Windows x64 ZIP without copying Linux environments."""
import argparse
from datetime import datetime, timezone
from email.parser import Parser
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import sqlite3
import subprocess
from zipfile import ZipFile, ZIP_DEFLATED


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_name(name):
    path = PurePosixPath(name)
    forbidden = re.compile(r'[<>:"\\|?*\x00-\x1f]')
    reserved = {'CON', 'PRN', 'AUX', 'NUL', *(f'COM{i}' for i in range(1, 10)), *(f'LPT{i}' for i in range(1, 10))}
    return (not path.is_absolute() and bool(path.parts) and all(
        part not in ('.', '..') and not forbidden.search(part)
        and not part.endswith((' ', '.')) and part.split('.')[0].upper() not in reserved
        for part in path.parts))


def unpack_wheels(wheels, target):
    versions = {}
    for wheel in sorted(wheels.glob('*.whl')):
        if not wheel.name.endswith(('-win_amd64.whl', '-any.whl')):
            raise ValueError('Unexpected dependency platform: ' + wheel.name)
        with ZipFile(wheel) as archive:
            metadata = Parser().parsestr(archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))).decode())
            versions[metadata['Name']] = {'version': metadata['Version'], 'wheel': wheel.name, 'sha256': digest(wheel)}
            for item in archive.infolist():
                if item.is_dir():
                    continue
                name = item.filename
                if not safe_name(name):
                    raise ValueError('Unsafe wheel entry: ' + name)
                parts = PurePosixPath(name).parts
                if parts[0].endswith('.data'):
                    if parts[1] in ('purelib', 'platlib'):
                        parts = parts[2:]
                    else:
                        # Retain licenses/data and unused CLI scripts without PATH installation.
                        parts = ('_wheel_data',) + parts
                dest = target.joinpath(*parts)
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(archive.read(item))
    return versions


def snapshot_data(source_root, dest_root):
    source_data, dest_data = source_root / '.local', dest_root / '.local'
    dest_data.mkdir(parents=True)
    with sqlite3.connect(source_data.joinpath('cockpit.sqlite').as_uri() + '?mode=ro', uri=True) as original:
        with sqlite3.connect(dest_data / 'cockpit.sqlite') as snapshot:
            original.backup(snapshot)
    for name in ('sources', 'uploads', 'exports', 'replays', 'evaluation', 'previews', 'reddit-runs'):
        folder = source_data / name
        if folder.exists():
            shutil.copytree(folder, dest_data / name, ignore=shutil.ignore_patterns('__pycache__', '*.pyc', '*.log', '.env*'))
    counts = {}
    with sqlite3.connect(dest_data / 'cockpit.sqlite') as db:
        for source_id, original, checksum in db.execute('SELECT id,path,checksum FROM sources').fetchall():
            path = Path(original)
            if not path.is_absolute():
                path = source_root / path
            relative = path.resolve().relative_to(source_data.resolve())
            retained = dest_data / relative
            if not retained.is_file() or digest(retained) != checksum:
                raise ValueError('Missing or altered retained document: ' + str(relative))
            db.execute('UPDATE sources SET path=? WHERE id=?', ('.local/' + relative.as_posix(), source_id))
        # Export records are append-only. Refuse rather than alter historical records.
        if db.execute('SELECT count(*) FROM exports').fetchone()[0]:
            raise ValueError('Existing exports need a reviewed path migration before packaging.')
        if db.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise ValueError('Database integrity check failed.')
        if db.execute('PRAGMA foreign_key_check').fetchall():
            raise ValueError('Database foreign-key check failed.')
        for table in ('sources', 'feedback', 'requirements', 'decisions', 'audit_events', 'rag_chunks'):
            counts[table] = db.execute(f'SELECT count(*) FROM {table}').fetchone()[0]
    return counts


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--python-zip', type=Path, required=True)
    parser.add_argument('--python-sha256', required=True)
    parser.add_argument('--wheels', type=Path, required=True)
    parser.add_argument('--launcher', type=Path, required=True)
    parser.add_argument('--go-license', type=Path, required=True)
    parser.add_argument('--stage', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if digest(args.python_zip) != args.python_sha256:
        raise ValueError('Python runtime checksum does not match.')
    if args.stage.exists() or args.output.exists():
        raise ValueError('Choose unused stage/output paths to preserve previous packages.')
    args.stage.mkdir(parents=True)
    app = args.stage / 'app'
    app.mkdir()
    files = subprocess.check_output(['git', 'ls-files', '-z'], cwd=root).decode().split('\0')
    for name in filter(None, files):
        if Path(name).name.startswith('.env') and Path(name).name != '.env.example':
            continue
        if not safe_name(name):
            raise ValueError('Source path is incompatible with Windows: ' + name)
        target = app / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(root / name, target)
    shutil.copytree(root / '.windows-web', args.stage / 'web')
    counts = snapshot_data(root, app)
    runtime = args.stage / 'runtime' / 'python'
    runtime.mkdir(parents=True)
    with ZipFile(args.python_zip) as archive:
        if not all(safe_name(n.rstrip('/')) for n in archive.namelist()):
            raise ValueError('Unsafe runtime archive.')
        archive.extractall(runtime)
    versions = unpack_wheels(args.wheels, runtime / 'Lib' / 'site-packages')
    pth = next(runtime.glob('python*._pth'))
    pth.write_text('python314.zip\n.\nLib/site-packages\n../../app\nimport site\n', encoding='ascii')
    shutil.copyfile(args.launcher, args.stage / 'Start BMW.exe')
    (args.stage / 'licenses').mkdir()
    shutil.copyfile(args.go_license, args.stage / 'licenses' / 'Go-LICENSE.txt')
    (args.stage / 'Start BMW.cmd').write_bytes(b'@echo off\r\ncd /d "%~dp0"\r\n"runtime\\python\\python.exe" -u "app\\scripts\\portable_server.py"\r\nif errorlevel 1 pause\r\n')
    (args.stage / 'settings.example.json').write_text(json.dumps({'OPENAI_API_KEY': '', 'OPENAI_MODEL': 'gpt-4.1-mini-2025-04-14'}, indent=2), encoding='utf-8')
    shutil.copyfile(root / 'docs' / 'WINDOWS_PORTABLE.md', args.stage / 'READ ME FIRST.txt')
    manifest = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'source_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root).decode().strip(),
        'platform': 'Windows 10/11 x64', 'python': '3.14.8',
        'python_sha256': args.python_sha256, 'dependencies': versions, 'data_counts': counts,
        'native_windows_run_verified': False,
        'files': {p.relative_to(args.stage).as_posix(): digest(p) for p in sorted(args.stage.rglob('*')) if p.is_file()},
    }
    (args.stage / 'BUILD-MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    names = set()
    with ZipFile(args.output, 'w', ZIP_DEFLATED, compresslevel=6) as archive:
        for path in sorted(args.stage.rglob('*')):
            if not path.is_file():
                continue
            name = 'BMW-G60-Windows/' + path.relative_to(args.stage).as_posix()
            if not safe_name(name) or name.casefold() in names or len(name) > 200:
                raise ValueError('Non-portable archive path: ' + name)
            names.add(name.casefold())
            archive.write(path, name)
    with ZipFile(args.output) as archive:
        if archive.testzip() is not None:
            raise ValueError('Archive CRC validation failed.')
    sha = digest(args.output)
    args.output.with_suffix('.zip.sha256').write_text(sha + '  ' + args.output.name + '\n')
    print(json.dumps({'zip': str(args.output), 'bytes': args.output.stat().st_size, 'files': len(names), 'sha256': sha, 'data_counts': counts}, indent=2))


if __name__ == '__main__':
    main()
