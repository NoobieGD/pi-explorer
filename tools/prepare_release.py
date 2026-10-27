"""Idempotent release text preparation. No external dependencies."""
from pathlib import Path
root=Path(__file__).resolve().parents[1]
path=root/'app/index.html'
html=path.read_text(encoding='utf-8')
html=html.replace('Native GMP, Chudnovsky binary splitting, integer square root, and 32 guard digits. Computation runs in a separate process. Cache loads are instant. The MPFR engine provides an independent comparison.',
    'Auto chooses native GMP for small jobs and the bundled multithreaded y-cruncher for large jobs. Decimal output is verified, and cached digits load instantly. Manual Chudnovsky and MPFR engines provide independent comparisons.')
if 'y-cruncher by Alexander' not in html:
    html=html.replace('Inspired by <a','Accelerated by <a href="https://www.numberworld.org/y-cruncher/" target="_blank" rel="noopener">y-cruncher by Alexander J. Yee</a>. Inspired by <a')
path.write_text(html,encoding='utf-8')
print('Release guide updated.')
