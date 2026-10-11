# BMW Product Intelligence — portable Windows edition

## Open the app

1. Right-click the ZIP and choose **Extract All**. Use a short, writable location such as `C:\BMW` or your Desktop.
2. Open the extracted **BMW-G60-Windows** folder.
3. Double-click **Start BMW.exe**. The dashboard opens in your default browser.
4. Keep the launcher window open. Press **Ctrl+C** there to stop the app.

Target: **Windows 10/11, Intel/AMD 64-bit (x64)**. Python and dependencies are bundled; no Node.js, Python installation, administrator access or first-run downloads are required. The launcher selects another local port if 3001 is occupied. The console displays the actual URL. Do not run files from inside the ZIP viewer.

The package contains the dark dashboard, all eleven panels, the original Python backend, RAG/review/collection code, G60 source documents, uploaded documents, current SQLite data and editable frontend source. The browser connects only to a local server bound to `127.0.0.1`.

The **hosted Sketchfab G60 needs internet and WebGL**. Its protected model remains hosted; its integration code is included. Local search, evidence, scoring and decisions work without internet. Live AI and Reddit collection need internet and your own valid OpenAI API credentials. No API keys are shipped.

## Optional live AI

Copy `settings.example.json` to `settings.json`, enter your own `OPENAI_API_KEY`, save and restart the launcher. Keep that file private. The Reddit collection form also accepts a key for a particular run. The existing failed-job history is retained from the working copy.

## Files and edits

- `Start BMW.exe`: native launcher; source is `app/scripts/windows_launcher.go`.
- `runtime/python/`: official embedded Python plus Windows dependency wheels, already unpacked.
- `web/`: compiled frontend used by the launcher.
- `app/`: complete editable source. Python edits apply after restarting the launcher.
- `app/.local/`: the packaged data snapshot and documents; new local changes are saved here.
- `startup.log`: launcher diagnostics, recreated on each start.
- `BUILD-MANIFEST.json`: source revision, dependency versions and file checksums.

Editing `app/src/` requires rebuilding `web/` with Node.js installed. From `app` in PowerShell:

```powershell
npm install
$env:BMWPM_WINDOWS_EXPORT='1'
npm run build
Remove-Item Env:BMWPM_WINDOWS_EXPORT
Copy-Item -Recurse -Force .windows-web\* ..\web\
```

Make a backup of the whole extracted folder before editing. Close the app before copying its data. The original Linux working folder and backup are separate from this package. Historical audit payloads may retain the paths they recorded; source document links are rebased by the portable launcher.

## Packaging and validation

Build the export using `BMWPM_WINDOWS_EXPORT=1 npm run build`. Build the launcher using Go with `GOOS=windows GOARCH=amd64 CGO_ENABLED=0`. Use `scripts/package_windows.py` with the verified Python runtime archive, launcher, Go license and Windows wheel directory to assemble a standard Deflate ZIP. Linux dependencies, Git history, credentials, test databases and caches are excluded.

The package can be inspected and tested from Linux, but a native Windows execution test is still required on a Windows PC. Windows may identify this locally built launcher as unsigned. No signing certificate is bundled.

Runtime sources: [Python embedded distribution](https://www.python.org/downloads/release/python-3148/) and [Go Windows cross-compilation](https://go.dev/wiki/WindowsCrossCompiling). Their bundled licenses and the dependencies' license metadata remain in the package.

Validation for this package: static frontend build, five relocation/archive tests, dependency closure for Windows x64, PE architecture/DLL inspection, archive CRC, and a relocated-copy check of all source downloads, local RAG search, PDF preview, dashboard panels, audit integrity and PowerPoint export. These application checks ran on Linux; the bundled Windows executable has not been run on Windows.
