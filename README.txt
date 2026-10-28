MULTI-CONSTANT EXPLORATION / VERSION 2.0.0
Choose pi, e, sqrt(2), sqrt(3), sqrt(5), or the golden ratio in the Number menu.
Reopen Start Pi Explorer to load the updated backend. Auto reuses optimized
native arithmetic; Exact GMP specializes its algorithm to each constant.
Caches, imports, exports and bookmarks preserve the identity and integer part.
Large completed datasets are protected from automatic small-cache eviction.
The standalone HTML and GitHub source upload copy are updated too.
Read MULTI-CONSTANTS.md for usage, verification and supported engines.

MEMORY MODE REPAIR / VERSION 1.8.2
Leaving Compact now restores the memory strategy selected before entering it,
rather than leaving Auto accidentally stuck in RAM-only mode. The compact
panel also has a "Use RAM-aware Auto" button, which selects both Auto engine
and Automatic memory without starting a calculation or changing the digit count.
The compact RAM estimate shows the count that fits the current budget. Compact
itself remains a RAM-only prototype; Auto/y-cruncher provide disk-backed blocks.

COMPACT ENGINE IN THE APP / VERSION 1.8.1
Select "Compact exact · experimental (RAM)" in the computation engine menu.
It removes common factors exactly and has been verified through 5 million
digits. Each app calculation compares every output digit with independent MPFR
before saving. Progress estimates and cancellation are supported. Actual RAM
and disk headroom are checked; this engine does not have disk-backed arithmetic.
It is slower than y-cruncher and is not used by Auto.
The "Check 200B / 210 GiB without computing" button performs only arithmetic
sizing checks. It reports NOT VERIFIED: no proven complete peak-workspace bound
or compact out-of-core backend exists. It never starts a calculation. The app
blocks unsupported 200B requests and preserves the active dataset.
Matching 210 GiB cannot be certified from small-run compression ratios or a
count of two idealized binary values. The target remains unverified and unmet.
The compact engine is desktop-only; the standalone HTML keeps its browser engine.

UNCAPPED GENERATION / VERSION 1.7.1
Experimental alternative arithmetic is in research/compact_engine.py.
See research/RESEARCH.txt and benchmarks/compact-research.json for the actual
measurements, storage-model limitations, and missing out-of-core backend.

The app no longer sets a digit-count ceiling. Enter any positive whole count;
10B, 100B, 200B and 1T shortcuts are included. Desktop count requests remain
exact decimal integers even beyond JavaScript's safe-number range. The native
worker and resource planner no longer enforce the old 1B or 12 GiB scratch caps.
Each run still checks actual free RAM, estimated scratch/output requirements,
and the 2 GiB free-space reserve before starting. Larger active datasets remain
protected from the managed-cache eviction budget. A request that cannot fit is
rejected for its resource requirements, not its number of digits.
Browser calculation/import presets are also uncapped; the browser engine's
memory, exact-number representation, maximum string length and storage still
apply. Use the desktop native engine for large calculations.
No large calculation was started for this change. 200B/1T/native configuration
planning was checked with mocked capacity, including an exact count above 2^53.

LIVE COMPUTATION PROGRESS / VERSION 1.5
The generation panel now shows the native phase, its real percentage when
y-cruncher reports one, time in the phase, total elapsed time, CPU activity,
resident RAM, and process read/write rates. A 45-second CPU history makes
long phases visibly active. The panel refreshes about 4 times per second;
the GUI polls every 200 ms while busy and every 1500 ms while idle.

The percentage is for the CURRENT PHASE, not the number of completed digits.
Phases without an exact native percentage use an indeterminate activity bar.
No ETA or digits-per-second figure is invented during intermediate arithmetic.
The previous verified dataset remains available until the new cache is complete.
The Windows approval step is shown as waiting for the calculator.

Native status is read incrementally from its live stream. The parent worker
no longer repeatedly reads the entire native log or rewrites unchanged phase
messages. The GUI reads telemetry directly, and overlapping status requests
are coalesced. Process counters use cached handles and direct Windows APIs.
Monitoring overhead was reduced; no further arithmetic speedup is claimed.

Two fresh 50M calculations matched the saved digits. The latest API trace
captured 142 unique snapshots, with 95% under 0.28 seconds old at receipt.
See benchmarks/live-progress.json for the actual measurements. CPU load
varied substantially; these runs do not establish a computation speedup.
The standalone HTML includes the faster polling and live elapsed time, with
browser progress labeled as an overall estimate. Windows process metrics
are available only in the desktop app.

NATIVE SSD TUNING / VERSION 1.4
Disk calculations now use parallel SSD I/O with 4 MiB of buffers instead of
the previous 64 MiB single-buffer defaults. Unused native checkpoint copies
are omitted. Native arithmetic verification and output checks remain enabled.
The calculator helper also uses less RAM by avoiding unnecessary math imports.

Eight fresh 25M calculations were verified against the existing digits while
testing CPU placement. The selected small-run median was 7.12 seconds versus
9.87 seconds for the old disk defaults, about 28% shorter in this comparison.
Timing varies with system load. Small-run CPU affinity applies only through
25M digits on this CPU; larger runs use native scheduling with SSD I/O tuning.

A fresh billion-digit attempt DID NOT finish within the 30-second deadline.
It was stopped and cleaned up; no cache hit was reported as fresh computation.
There is no guarantee of 1B/30s irrespective of CPU, RAM, storage or system load.
See benchmarks/FASTEST-RESULTS.txt and fastest-native.json for the measurements.
Tune for This PC.cmd repeats the bounded comparison with Windows approval.

RAM-AWARE GENERATION AND SMOOTH ZOOM / VERSION 1.3
Automatic measures free RAM and chooses a RAM calculation or disk-backed blocks.
The disk algorithm treats RAM as a bounded working cache and streams arithmetic
blocks through temporary files. It does not restart pi from zero for every chunk.
Only complete, verified output becomes the displayed dataset. The previous
dataset stays available while a new calculation is in progress.

The generation panel shows the RAM budget, temporary disk cap and final cache size.
One billion digits reserve up to 10.37 GiB including temporary files and output;
the native planner reports about 4.59 GiB scratch + 954 MiB output at 128 MiB RAM.
The app keeps 2 GiB of disk space free and stops at the temporary-space limit.
Scratch is cleared on completion, cancellation and normal shutdown. The native
helper also stops and cleans up if its owning worker exits unexpectedly.
Newly managed digit caches share a 2 GiB budget. Older inactive managed entries
can be evicted; the current dataset, bundled seed and imported files are protected.
Legacy caches that predate managed-cache metadata are also preserved.

Windows requires administrator approval for y-cruncher disk mode. Approve the
standard Windows prompt when starting a disk-backed calculation. Only the narrow
calculator helper is elevated; the server and GUI keep their normal permissions.
Cancelling the prompt preserves the existing cache. The native requirement is
documented at https://www.numberworld.org/y-cruncher/guides/swapmode.html

Zoom now blends four text detail levels: full glyphs, fine glyphs, microglyphs,
and a row overview. The small glyph levels are mipmaps of the actual bundled font.
The overview averages font coverage by row. Its quiet bands are not fabricated
character-dependent noise. Raster history uses a 24 MiB memory budget.
The standalone HTML includes the same four LODs; native disk-backed computation
requires the desktop app. Browser computation remains capped at one million.

Validation: a real disk-mode one-million-digit calculation at a 128 MiB working
budget matched all digits from independent MPFR. Its scratch files were removed.
See benchmarks/disk-validation.json. A subsequent 125M run completed with a
380 MiB working budget; its first 100M matched the prior RAM cache and scratch
was removed. See benchmarks/disk-125m-validation.json. 41 automated tests passed.
The billion-digit <60s target remains
unverified; disk-backed computation can be substantially slower than RAM.

HISTORICAL PERFORMANCE UPDATE / VERSION 1.2
Native digit files are memory mapped, including native files beginning with 3.
View changes convert only the visible, sampled tile using native NumPy operations.
Color/pixel views cache a raster layer; zoom/pan no longer redraw every cell.
Digit/text/shape searches and statistics use bounded-memory chunks. Native export
streams directly to the browser download instead of building a billion-byte Blob.
Native computation runs at normal process priority, with output verification on.
The former desktop request limit has been removed in version 1.7.1.
GMP/MPFR use RAM preflight for large requests; Auto prefers native y-cruncher.
Select "Fresh calculation" to bypass cached results when measuring computation.

The 1-billion-under-60-seconds target has NOT been verified on this computer.
y-cruncher's 1B plan requires 4.54 GiB; only about 0.8-0.9 GiB was available.
Run "Benchmark 1 Billion.cmd" after closing memory-heavy apps/Codex to attempt
a fresh, verified run independently of this chat. Its result is saved to
benchmarks/billion-latest.json. Cached loading is never counted as computation.
See benchmarks/RESULTS.txt for measured timings and their limits.

RESTART REPAIR / VERSION 1.1
Session expiry now reconnects automatically. Reopening the desktop launcher forces
a fresh navigation even when Edge reuses an existing window. Rejected HTTP requests
close their unread connections. Windows progress-file locks no longer abort math;
progress writes are best effort and final cache writes retry brief file locks.
Your existing digit files are preserved.

STANDALONE HTML
HTML Version/index.html is a self-contained 5.2 MB app with the same GUI and
5 million bundled digits. Open it directly, or upload it to a static web host.
Pi Explorer - Static Website.zip contains index.html and hosting instructions.
Browser computation uses exact BigInt Chudnovsky with no preset digit ceiling;
the desktop version retains y-cruncher/GMP/MPFR acceleration. No Python server
is required for the HTML version.

PI EXPLORER
A universe in a number.

START
Double-click "Start Pi Explorer.vbs" in this folder.
"Start Pi Explorer.cmd" is an alternative launcher.
The app opens in its own Microsoft Edge window. Chrome or your default browser
is used when Edge is unavailable. No Python installation or internet is needed.
Windows 10/11, 64-bit. The bundled embedded Python runtime stays in this folder.

Five million actual decimal places are already computed and cached. They load
immediately. All computation, search, image conversion, and storage stay local.
The server binds only to 127.0.0.1:31415. No accounts, telemetry, or cloud service.

COMPUTE
Choose a digit count, then Calculate pi. Auto uses native GMP for small requests
and the bundled multithreaded y-cruncher accelerator for 2 million or more digits.
Manual engines: y-cruncher, Chudnovsky/GMP, and MPFR. Auto falls back to GMP if
the accelerator cannot run. Choosing a different manual engine recomputes the
digits and compares them against the existing cache before replacing it.

Chudnovsky uses binary splitting, an exact integer square root, exact integer
division, and 32 guard digits. MPFR provides an independent implementation.
y-cruncher chooses a CPU-specific SIMD binary and verifies decimal output.
The optional benchmark hardware-inventory stage is stopped after successful
digit verification because Windows WMI can take a long time on some machines.
This app does not produce a complete y-cruncher world-record submission report.

The desktop interface accepts any positive whole digit count. Larger computations take
more memory and time. This is a practical desktop explorer, not a claim of the
world's fastest implementation on every machine. You can also import externally
computed decimal digits from a plain text file. The first 50 imported digits are
checked; the remainder is user supplied and is not independently verified.

SEARCH
Digits: enter a number, birthday, sequence, or other decimal pattern.
Text: every pair of digits becomes a number modulo 26. 00=A, 01=B, ... 25=Z,
26=A, ... 99=V. This reproduces the main word searches in the reference video.
Alternate encodings: A1Z26 (invalid pairs become dots), and three-digit ASCII
(nonprintable codes become dots). Pairing may be shifted by one decimal digit.
Shape: draw or import an image into a 4x4 to 16x16 editor. White editor pixels
mean on; dark pixels mean off. The default mapping is 0-4 black, 5-9 white.
Odd/even mapping is available in Field guide. Imported images are resized with
their aspect ratio preserved and converted to a thresholded monochrome pattern.
Dark imported image areas become white pattern cells. Review the editor first.

Crop empty border removes unused surrounding black rows and columns. All black
and white cells INSIDE the remaining rectangle must match. A shape never wraps
across a row edge. Width sweep tests every width in the selected inclusive range
(up to 1,024); turning it off searches the current canvas row width only.
Native GMP bit masks intersect millions of candidate locations at once.

Numeric/text searches report up to 300 overlapping matches. Shape searches report
up to 60 matches. When the result limit is reached, the UI displays a '+' and
explains that the results are capped. Shape results are sorted by position within
the widths examined before the cap; they are not necessarily the earliest global
matches if the sweep ends at the cap. Text results show BOTH character position
and original decimal-digit position. Decimal position 1 is the first 1 after 3.
Click a result to fly to it. Shape results also set the discovered row width.

EXPLORE
Drag the canvas to pan. Scroll to zoom at the pointer. Shift+scroll travels along
the grid. Double-click a cell to inspect its original decimal position.
The slider travels through the computed digits. "Go to digit" accepts commas.
Row width reflows the SAME digit stream; it does not change pi.
Digits, Letters, Color, and Pixels are four views of the same data.
F = focus canvas; 0 = fit width; Home = return to beginning; +/- = zoom;
arrow up/down = travel; Enter = search; Escape = close inspection/focus mode.
Generation controls collapse after a search to leave room for results. Click
"01 / GENERATE" to expand them again.

Bookmark saves the current view in the local browser profile. Distribution shows
digit counts, entropy, chi-square, the longest repeated digit run, and SHA-256.
Capture exports the current canvas to PNG. Export pi saves "3." plus your digits.
Sound effects are original synthesized tones with mute and master-volume controls.
Six WAV versions are included in app/sounds; the UI synthesizes them live.

QUIT
Open Field guide and click "Quit local engine", then close the window.
Closing only the window leaves the small local engine ready for the next launch.
Launching the app again reuses the existing engine, rather than starting duplicates.

VALIDATION
Run "Run tests.cmd" for numerical and encoding tests, including 10,000-digit
independent MPFR agreement and randomized bit-mask vs brute-force shape searches.
tests/smoke_api.py exercises the running server and verifies search results.

Observed on this computer during development:
- 5,000,000 digits with y-cruncher: 3.45 seconds through app save and verification;
  y-cruncher's arithmetic + decimal conversion time was 1.417 seconds.
- All 5 million digits matched the GMP implementation byte-for-byte.
- Cropped 5x5 pi symbol, all row widths 6-320: 47 matches in about 5.6 seconds.
Timings vary with CPU load and hardware. Cached digits do not need recomputation.

REFERENCE
Nateate, "I Built a Program to Find Hidden Patterns in Pi":
https://www.youtube.com/watch?v=wxBWOvELdgk

The complete available transcript was analyzed and representative frames at 1:15,
1:35, 4:20, 5:30, 8:05, and 9:12 were inspected. The app follows the video's
near-black canvas, muted monospace digits, gold highlights, camera flights,
decimal/letter/color/binary views, and variable-width drawable shape search.
It is an independent implementation inspired by that video.

Reproduced discoveries (positions start at 1, after the decimal point):
12345: digit 49,702
999999: digit 762
PIE: character 10,962, decimal digit 21,923
CAT: character 22,731, decimal digit 45,461
DOG: character 44,145, decimal digit 88,289
MATH: character 91,682, decimal digit 183,363
The video appears to change pair alignment for NATE; this app makes alignment
explicit, so positions stay reproducible.

MATHEMATICAL NOTE
Pi is irrational and its decimal expansion is nonperiodic. Whether pi is normal
is unproved. Infinity and nonperiodicity alone do not imply every finite message
or image occurs. The probability estimates are heuristics assuming independent
uniform digits. Modulo-26 letters are slightly biased because 100 isn't divisible
by 26. A finite pattern search cannot prove that pi contains every possible image.

THIRD-PARTY COMPONENTS
y-cruncher 0.8.7.9547b by Alexander J. Yee, downloaded from the author's official
GitHub release. Free for personal noncommercial and academic use under its own
license; commercial use requires contacting the author. The complete license is
in vendor/y-cruncher/y-cruncher v0.8.7.9547b/Read Me.txt.
https://www.numberworld.org/y-cruncher/
https://github.com/Mysticial/y-cruncher/releases/tag/v0.8.7.9547b

gmpy2 2.3.2 / GMP 6.3.0 / MPFR 4.2.2: licenses included in vendor.
Python 3.12.10 embedded runtime: runtime/LICENSE.txt.
JetBrains Mono: app/fonts/OFL.txt (SIL Open Font License).
The original app source and synthesized sound effects are included for editing.

FAST SEARCH / VERSION 1.6.2
The desktop search engine now uses an original AVX2 C scanner with a portable
scalar fallback, called directly against the memory-mapped digit file. Searches
share a bounded eight-thread pool. Digits and modulo-26 text default to four
workers, which tested well on this hybrid CPU; ASCII and pixel sweeps can use
all eight. Scanner worker threads request Windows HighQoS at normal priority,
so the hidden GUI backend does not rely on inferred background power policy.
The GIL is released during native scanning. No billion-byte copies
or complete decoded text files are made for a query.

Decimal searches use SIMD candidate filters followed by exact verification.
Modulo-26 text compares digit pairs with exact vector arithmetic. ASCII and
A1Z26 words without a dot search their unique decimal encodings directly at
the chosen alignment. Dot substitution and mixed encodings retain exact search
semantics. Overlapping matches and chunk-boundary matches are retained.
Pixel searches use native masks, wildcard cells and global row-edge checks.

The last 64 exact query results are cached in a small bounded RAM LRU. The key
includes the mapped file identity, size, modification time, encoding, alignment
and result limit. Dataset changes clear the cache. Cached results are labeled
as reuse and never reported as a fresh scan throughput. Capped searches report
their actual covered range, rather than pretending to scan the entire file.

Windows read-ahead hints are bounded to the current tasks on files over 2 GiB.
They may help streaming disk I/O, but cannot make disk throughput equal RAM.
The native offset API is 64 bit. Existing larger plain ASCII digit files can
be placed in data/ as pi-<count>.txt; the launcher opens the largest file with
a valid pi prefix without copying it into RAM. Opening such a file does not
calculate any new digits. Imported files
are prefix-checked; verify their provenance separately if required.

Benchmark Scanning.cmd measures existing data only. It writes results to
benchmarks/scan-speed.json. tools/validate_scan_api.py checks the complete HTTP
search path on an ephemeral localhost port, using existing digits only.
benchmarks/scan-api.json includes every measured trial, cache flags and ranges.
tools/validate_scan_live.py measures distinct complete queries through the
running desktop backend; raw results are in benchmarks/scan-live.json.
The results and their limits are summarized in benchmarks/SCAN-RESULTS.txt.
Warm mapped files and cold disk reads differ substantially. A rate measured
on a resident 1 GB file is not a guarantee for a 200 GB file. No 200-billion-digit
calculation or dataset was created for this update.

The native build is reproducible with Zig 0.15.2:
powershell -File tools/build_scan.ps1 -Zig <path-to-zig.exe>
Source: native/scan.c. Runtime license: native/LICENSE.txt.
The self-contained browser HTML retains its browser engine; the Windows DLL
acceleration applies to the desktop application.

FILES
app/          GUI, canvas renderer, font, original sound files
engine.py     Computation, encodings, statistics, native bit-mask shape search
server.py     Local HTTP API, computation/search jobs, cache, desktop launch
data/         Cached digits, SHA-256 metadata, native computation logs
runtime/      Self-contained official Python embedded runtime
vendor/       Native libraries and y-cruncher, with their licenses
tests/        Precision, encoding, shape, and API tests
reference/    Reference-analysis notes
