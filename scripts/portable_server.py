"""Serve the exported UI and original API from a movable, local-only package."""
import argparse
import json
import os
from pathlib import Path
import socket
import sqlite3
import sys
import threading
import time
import webbrowser


def relocate_sources(root):
    """Only rebase file pointers; preserve evidence, decisions and audit content."""
    database = root / '.local' / 'cockpit.sqlite'
    if not database.is_file():
        raise RuntimeError('The bundled database is missing. Extract the entire ZIP first.')
    with sqlite3.connect(database) as db:
        for source_id, original in db.execute('SELECT id, path FROM sources').fetchall():
            normalized = original.replace('\\', '/')
            if '/.local/' in normalized:
                normalized = '.local/' + normalized.split('/.local/', 1)[1]
            candidate = (root / normalized).resolve()
            if not candidate.is_relative_to(root / '.local') or not candidate.is_file():
                raise RuntimeError('A bundled source document is missing. Extract the entire ZIP again.')
            relative = candidate.relative_to(root).as_posix()
            if relative != original:
                db.execute('UPDATE sources SET path=? WHERE id=?', (relative, source_id))


def create_app(web_root):
    from backend.app import app
    from starlette.staticfiles import StaticFiles

    class ExportedUI(StaticFiles):
        async def get_response(self, path, scope):
            # Next's static export emits /cockpit as cockpit.html.
            if path == 'cockpit':
                path = 'cockpit.html'
            return await super().get_response(path, scope)

    # Only web assets are exposed, never the application source or database.
    app.mount('/', ExportedUI(directory=web_root, html=True), name='portable-ui')
    return app


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--no-browser', action='store_true')
    parser.add_argument('--port', type=int, default=3001)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    web_root = root.parent / 'web'
    if not (web_root / 'index.html').is_file():
        raise RuntimeError('The dashboard files are missing. Extract the entire ZIP first.')
    os.chdir(root)
    sys.path.insert(0, str(root))
    os.environ['BMWPM_DATA_DIR'] = str(root / '.local')
    os.environ.pop('BMWPM_DATABASE_URL', None)
    os.environ['PYTHONIOENCODING'] = 'utf-8'
    settings_file = root.parent / 'settings.json'
    if settings_file.is_file():
        settings = json.loads(settings_file.read_text(encoding='utf-8-sig'))
        for key in ('OPENAI_API_KEY', 'OPENAI_MODEL', 'BMWPM_REDDIT_MODEL', 'BMWPM_CATEGORIZER_MODEL'):
            value = settings.get(key)
            if isinstance(value, str) and value.strip():
                os.environ[key] = value.strip()
    relocate_sources(root)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        if os.name == 'nt':
            listener.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        try:
            listener.bind(('127.0.0.1', args.port))
        except OSError:
            listener.bind(('127.0.0.1', 0))
        port = listener.getsockname()[1]
        os.environ['BMWPM_WEB_PORT'] = str(port)
        from alembic import command
        from alembic.config import Config
        command.upgrade(Config(str(root / 'alembic.ini')), 'head')
        import uvicorn
        server = uvicorn.Server(uvicorn.Config(create_app(web_root), host='127.0.0.1', port=port, log_level='warning'))
        url = f'http://127.0.0.1:{port}/'
        print(f'BMW Product Intelligence\n\nOpen {url}\nKeep this window open. Press Ctrl+C to stop.\n', flush=True)

        def open_browser():
            for _ in range(300):
                if server.started:
                    webbrowser.open(url)
                    return
                if server.should_exit:
                    return
                time.sleep(0.1)

        if not args.no_browser:
            threading.Thread(target=open_browser, daemon=True).start()
        server.run(sockets=[listener])


if __name__ == '__main__':
    main()
