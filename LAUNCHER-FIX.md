# Windows setup and launcher fix

Python 3.12 is no longer mandatory. Use 64-bit Python 3.11, 3.12, 3.13 or 3.14.

1. Extract this entire source folder from the ZIP. Do not run commands inside the ZIP viewer.
2. Run **Setup Pi Explorer.cmd** and wait for **Setup complete**.
3. Run **Start Pi Explorer.cmd**. Keep its window open while using the app.

All six CMD entry points share `tools/source_launcher.ps1`. The VBS launcher now shows the same startup/error window. No launcher assumes setup already succeeded. Missing or moved environments are rebuilt; an existing broken environment is preserved as `.venv-backup-*`. Installations without the `py` command are supported through python/python3 or the Windows Python registry. For a custom Python location, set PI_EXPLORER_PYTHON to the full path of python.exe.

Checks: a clean installation, repeated CMD setup, dependency/application imports, clear missing-interpreter failure, and isolated HTTP startup passed using Python 3.12.14. Both pinned dependencies publish standard Python 3.14 Windows x64 wheels. An installed Python 3.14 interpreter was not available in the test environment, so a full 3.14 runtime test was not performed. No large calculation was run, and no running API was restarted.

Replace all six CMD files, Start Pi Explorer.vbs, and add tools/source_launcher.ps1 in an existing checkout. Or extract the updated full ZIP. The GitHub repository still needs these updated files uploaded; rebuilding this local package does not publish it online.
