# v1.1.3 — Faster desktop searches

## Changelog

- Search mapped TXT digits and color sequences without copying or transforming complete chunks.
- Search unambiguous ASCII and A1Z26 text directly as encoded digit patterns, preserving character alignment and overlapping matches.
- Reuse exact results for unchanged datasets on the source-only fallback and packed YCD/MPT paths, with a bounded 64-entry shared LRU cache.
- Preserve cancellation, first-N result limits, chunk-boundary matches and source-file identity checks.
- Keep ambiguous text patterns on the existing decoder so ASCII dots and A1Z26 placeholders retain their original meaning.
- Add correctness tests for encoding/alignment, overlapping matches, cancellation, caching and a 16 MiB boundary.

## Measured results

Synthetic 64 MiB TXT dataset, warm OS cache, optional DLL disabled; medians of three full no-match scans compared against v1.1.2:

| Search | Before | After | Speedup |
| --- | --- | --- | --- |
| digits / mod26 | 101.5 ms | 27.5 ms | 3.70x |
| text / ascii | 436.2 ms | 38.9 ms | 11.21x |
| text / a1z26 | 359.3 ms | 44.6 ms | 8.06x |
| text / mod26 | 370.9 ms | 364.1 ms | 1.02x |

Repeated exact queries completed in approximately 0.7–1.2 ms using the result cache. This is cache lookup time, not scan throughput. First-time mod26 performance is essentially unchanged. Packed-file first scans and the optional native DLL are not claimed to have these speedups. Results do not establish cold-disk or 62-billion-digit throughput. The raw measurements are in benchmarks/search-v1.1.3.json.

## Validation

86 tests ran successfully; 10 optional native tests were skipped. No large pi calculation was started.

## Update

Download the updated source or pull main, then close and reopen the desktop app. Preserve your data, y-cruncher installation and Python environment. This release updates the desktop computation/exploration app, not the separate Pi Atlas public API.
