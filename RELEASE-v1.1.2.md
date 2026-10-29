# v1.1.2 — Native engine and benchmark fixes

## Changelog

- Detect separately installed y-cruncher distributions instead of requiring one exact folder name.
- Support an explicit executable path through PI_EXPLORER_YCRUNCHER.
- Prevent large worker error messages from deadlocking calculation startup.
- Stop native launches that produce no output for 45 seconds and display actionable diagnostics.
- Keep calculation errors visible and save native job logs.
- Prevent one Pi Explorer installation from opening or stopping another installation's server.
- Remove tuning's dependency on a private 200-million-digit reference file; use an independent MPFR prefix when absent.
- Support TXT, YCD and MPT datasets in scanning benchmarks and explain missing datasets clearly.
- Add regression tests for startup failures, silent processes, installation discovery and error output.

## Validation

The previous full run covered 82 tests, with 10 optional tests skipped. Five focused startup tests, including an additional process-launch failure test, passed after final review. A real 10,000-digit y-cruncher RAM calculation verified successfully using release 0.8.7.9547b. Tuning preflight passed without starting a benchmark. No billion-digit benchmark was run.

## Updating

Replace the source files while keeping your existing data and complete y-cruncher installation. Close and reopen the app. Other y-cruncher releases may require compatibility changes.
