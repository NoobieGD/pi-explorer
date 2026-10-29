# pi-explorer
most optimized computing system i can make for pi digits in both speed and storage

## Run on Windows

Extract the complete source folder, run **Setup Pi Explorer.cmd**, then **Start Pi Explorer.cmd**. The setup launcher detects Python rather than requiring a separate Python 3.12 installation. See [launcher instructions](LAUNCHER-FIX.md).

## y-cruncher and benchmarks

Extract the complete official y-cruncher distribution, including its Binaries folder, under `vendor/y-cruncher/`. A single installation is detected automatically. For another location or several copies, set `PI_EXPLORER_YCRUNCHER` to the full `y-cruncher.exe` path before starting the app. This integration was verified with release 0.8.7.9547b.

Native errors stay visible in the app and `data/last-computation-error.log`. A silent native launch times out after 45 seconds; active calculations are not limited to 45 seconds. Large diagnostic output is drained continuously so it cannot block the worker monitor.

Tuning works without a private reference dataset. Scan benchmarking accepts existing TXT, YCD and MPT datasets. Run `python benchmarks/tune_native.py --check` for preflight without starting a calculation. The full tuner still runs its advertised benchmarks.

See [native startup fixes and validation](NATIVE-STARTUP-FIX.md) and [supported constants](MULTI-CONSTANTS.md). Computed datasets, scratch files, virtual environments and third-party executables are excluded from this repository.
