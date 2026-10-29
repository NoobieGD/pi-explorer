# y-cruncher startup and benchmark fixes

Close the GitHub-source app, replace the updated source files, then reopen Start Pi Explorer.cmd. Keep your existing data and complete y-cruncher installation.

Updated runtime files: engine.py, native_runner.py, native_install.py (new), server.py, app/app.js. Updated benchmark scripts: benchmarks/tune_native.py, benchmarks/billion.py, benchmarks/scan_speed.py. README.md explains native installation discovery and logs. The ZIP contains all updated source files; no native executable or large dataset is redistributed.

A single y-cruncher.exe under vendor/ or y-cruncher/ is detected automatically. Extract the whole official archive, including Binaries. For a different location or several installations, set PI_EXPLORER_YCRUNCHER to the complete executable path and restart. CLI compatibility was tested with the integrated official release 0.8.7.9547b, not every later version.

Errors remain visible in the app and data/last-computation-error.log. Native job logs are data/native-output/run-*/stdout.log and runner-result.json. Silent launches time out after 45 seconds. Large error output cannot block the process monitor. Different source installations no longer accidentally open or stop each other's server.

Tuning now uses an independent 100K MPFR reference prefix when the owner's private 200M reference is absent. It retains native verification. Scanning accepts existing TXT/YCD/MPT files and reports missing datasets clearly.

Validation: 82 source tests ran successfully (10 optional tests skipped); large-stderr deadlock, missing installation, alternative distribution paths and silent startup regressions pass. A real 10,000-digit RAM-mode y-cruncher output was verified, tuning preflight passed without calculation, and a separate app startup preserved an existing local server. No billion-digit benchmark or large dataset calculation was run. Python 3.14 was not available for an actual runtime test.

This changes the local upload folder and ZIP. GitHub must still receive these updated source files.
