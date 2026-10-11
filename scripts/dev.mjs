import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
const root = process.cwd();
const apiPort = process.env.BMWPM_API_PORT || '8001';
const webPort = process.env.BMWPM_WEB_PORT || '3001';
process.env.BMWPM_API_URL ||= `http://127.0.0.1:${apiPort}`;
const webMode = process.argv.includes('--production') ? 'start' : 'dev';
const python = process.env.BMWPM_PYTHON || path.join(root, '.venv', process.platform === 'win32' ? 'Scripts/python.exe' : 'bin/python');
if (!existsSync(python)) throw new Error('Run the setup steps in README.md to create .venv first.');
const children = [
  spawn(python, ['-m', 'uvicorn', 'backend.app:app', '--host', '127.0.0.1', '--port', apiPort], { stdio: 'inherit', windowsHide: true }),
  spawn(process.execPath, [path.join(root, 'node_modules/next/dist/bin/next'), webMode, '--hostname', '127.0.0.1', '--port', webPort], { stdio: 'inherit', windowsHide: true }),
];
let stopping = false;
function stop(code = 0) { if (stopping) return; stopping = true; for (const child of children) child.kill(); setTimeout(() => process.exit(code), 500); }
process.on('SIGINT', () => stop()); process.on('SIGTERM', () => stop());
for (const child of children) { child.on('error', e => { console.error(e.message); stop(1); }); child.on('exit', code => stop(code || 0)); }
