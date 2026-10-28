# Multi-constant Pi Explorer — version 2.0.0

The desktop app and standalone HTML now compute and explore **π, Euler's number e, √2, √3, √5, and the golden ratio φ**. Euler's number here is e ≈ 2.71828, not the Euler–Mascheroni constant.

## Use it

1. Reopen **Start Pi Explorer.cmd** to load the updated desktop backend. Refresh an already open app window if needed. The separate Pi Atlas public API is unchanged.
2. Choose the **Number** above Decimal places, then choose a precision. **Auto** selects the optimized native calculator for larger requests or when the exact in-memory method cannot safely fit.
3. Keep memory on **Automatic**, or select disk-backed computation when required. The usual resource checks, progress display, cancellation and verification remain active.
4. Click Calculate. The previous dataset remains visible and correctly labelled until verified output is ready. Digits, letters, colors, pixels, pan/zoom, highlights, search and statistics work for every supported constant.

**Exact GMP** uses the appropriate mathematical algorithm for the selected constant. **MPFR** provides an independently implemented comparison. For native compressed output, choose the packed YCD option. Its reduced Chudnovsky formula is specific to π; other constants use their own native algorithms and packed output. TachusPI and the experimental Compact engine remain π-only and are disabled for other constants.

## Algorithms and correctness

- π keeps the existing Chudnovsky, native y-cruncher, MPFR, Compact and optional TachusPI paths.
- e uses balanced binary splitting of the factorial series. Exact lower and upper rational remainder bounds must certify the same decimal integer before digits are returned.
- Square roots use GMP's exact integer square root of `radicand × 10^(2 × decimalPlaces)`. The golden ratio derives its exact decimal integer from the integer square root of five. There is no floating-point approximation in these paths.
- The MPFR comparison computes directed lower and upper bounds and checks that their truncated decimal integers agree.
- Large native calculations reuse y-cruncher's specialized e/square-root/golden-ratio algorithms, CPU dispatch, parallel tasks, disk-backed arithmetic, existing SSD configuration, native output checks, cancellation, telemetry and zero-copy cache commit. No additional calculator package is needed in the normal installed app.
- Some square roots have no bundled native spot-check reference. They require a clean native exit after both base-conversion and saved-output checks, plus the app's constant-prefix/length validation. A full independent MPFR comparison was performed in validation; huge production runs do not silently perform a second full calculation.

The native constant names/configuration syntax were checked against the installed y-cruncher and its official documentation: [command/custom-formula interface](https://www.numberworld.org/y-cruncher/guides/custom_formulas.html), [function reference](https://www.numberworld.org/y-cruncher/guides/custom_formulas_list.html). No claim is made to beat y-cruncher's large-scale arithmetic or guarantee a fixed time across hardware.

## Separate datasets and integer parts

Digits are stored after the decimal point, with positions starting at one. The display and exports use each constant's correct integer part: `3.`, `2.` or `1.`. Example filenames:

```text
data/pi-1000000.txt
data/e-1000000.txt
data/sqrt2-1000000.ycd
data/phi-1000000.ycd
```

Constant identity participates in cache paths, metadata, browser cache keys and dataset changes. Equal digit counts never make different numbers share a cache. Imports validate the selected constant's prefix; choose the intended Number before importing. Export filenames and integer prefixes identify the current displayed dataset. Bookmarks record their constant and cannot silently open on another number.

The desktop remembers the last active dataset for its next launch. Old Pi filenames still work. Your 27-billion and 62.83-billion digit files are retained; completed files larger than the automatic small-cache budget are protected from automatic eviction. Smaller managed caches retain the existing quota policy. Free-space checks still account for the actual files on disk.

## Standalone and GitHub copy

**HTML Version/index.html** has the same selector and exact BigInt algorithms. It keeps separate constant/count identities, imports and exports correct prefixes, and can restore the last constant. The bundled five-million-digit sample is still π. Browser memory, BigInt/string limits and available storage still apply; native disk-backed calculations are desktop-only.

The **Pi Explorer - GitHub Upload** folder contains the updated source and HTML, without your full datasets, local settings, runtimes or third-party executables. Its `.venv` setup/launchers remain adapted for a source-code checkout. Replace its contents in your separate source repository, including `.gitignore`; this does not update the Pi Atlas search website or publish an API.

To rebuild the standalone HTML from source, `tools/build_html.py` uses a local verified five-million-digit Pi seed. If only the existing standalone HTML is available, its embedded seed can be reused; rebuilding never calculates a new seed.

## Validation

Fresh 100,000-digit calculations of all six constants agreed in full across exact GMP, directed MPFR, and native compressed YCD output. The browser's 100,000-digit e/√2/φ results matched independently validated SHA-256 hashes. Exact square-root inequalities, cross-constant cache separation, import/export prefixes, native configuration, unsupported engines, startup metadata and large-cache preservation have tests.

Timing and verification records are in `benchmarks/irrational-constants-2026-10-28.json`. Timings for native arithmetic exclude process startup and must not be presented as total app elapsed time. No billion-digit or larger calculation was started for this update. Resource estimates remain conservative estimates; the old 200B/210 GiB target is not established for these new constants.
