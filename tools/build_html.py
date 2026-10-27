"""Bundle the existing GUI, verified digits, browser workers and font into one HTML."""
from pathlib import Path
import base64, re, json, zipfile, hashlib
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'HTML Version'
OUT.mkdir(exist_ok=True)
html=(ROOT/'app/index.html').read_text(encoding='utf-8')
css=(ROOT/'app/style.css').read_text(encoding='utf-8')+'\n'+(ROOT/'app/live.css').read_text(encoding='utf-8')
font=base64.b64encode((ROOT/'app/fonts/JetBrainsMono-Regular.woff2').read_bytes()).decode()
css=css.replace('fonts/JetBrainsMono-Regular.woff2','data:font/woff2;base64,'+font)
script="'use strict';\n"+(ROOT/'app/viewport.js').read_text(encoding='utf-8')+'\n'+(ROOT/'app/compute-live.js').read_text(encoding='utf-8')+'\n'+(ROOT/'app/app.js').read_text(encoding='utf-8')
html=html.replace('<option value="compact">Compact exact · experimental (RAM)</option>','')
html=re.sub(r'(<select id="engineSelect"[^>]*>).*?(</select>)',r'\1<option value="browser">Chudnovsky · browser worker</option>\2',html,flags=re.S)
engine=(ROOT/'portable/portable-engine.js').read_text(encoding='utf-8')
bridge=(ROOT/'portable/portable-bridge.js').read_text(encoding='utf-8')
seed=ROOT/'data/pi-5000000.txt'
if seed.exists():digits=seed.read_text(encoding='ascii')
else:
    # Reuse a prefix of an existing larger verified file; never calculate digits.
    source=next(p for p in sorted((ROOT/'data').glob('pi-*.txt')) if p.stat().st_size>=5000000)
    with source.open('rb') as stream:
        prefix=stream.read(2);stream.seek(2 if prefix==b'3.' else 0)
        digits=stream.read(5000000).decode('ascii')
assert len(digits)==5000000
assert hashlib.sha256(digits.encode()).hexdigest()=='e157d93a29d97005bf60b78d4a2071340eec92d50830012499be00afae1b66c3'
icon=base64.b64encode((ROOT/'app/pi-explorer.ico').read_bytes()).decode()
html=re.sub(r'<link rel="icon"[^>]+>','<link rel="icon" href="data:image/x-icon;base64,'+icon+'">',html)
html=html.replace('<link rel="stylesheet" href="style.css">','<style>'+css+'</style>')
html=html.replace('<link rel="stylesheet" href="live.css">','')
html=html.replace('value="5000000" autocomplete="off"','value="1000000" autocomplete="off"')
html=html.replace('step="1000000"','step="100000"')
html=html.replace('<option value="auto">Auto · fastest available native engine</option><option value="ycruncher">y-cruncher · parallel CPU acceleration</option><option value="chudnovsky">Chudnovsky · native GMP</option><option value="mpfr">MPFR · independent comparison</option>',
 '<option value="browser">Chudnovsky · browser worker</option>')
html=html.replace('data-count="1000000">1M','data-count="250000">250K')
html=html.replace('data-count="5000000" class="active">5M','data-count="500000">500K')
html=html.replace('data-count="10000000">10M','data-count="1000000" class="active">1M')
html=html.replace('<button data-count="100000000">100M</button>','').replace('<button data-count="1000000000">1B</button>','')
for count in ('10000000000','100000000000','200000000000','1000000000000'):
 html=re.sub(r'<button data-count="'+count+r'">[^<]+</button>','',html)
html=html.replace('NATIVE PRECISION ENGINE','BROWSER PRECISION ENGINE')
html=html.replace('<div id="memoryControls"','<div hidden id="memoryControls"')
html=html.replace('Calculate 5 million digits ↗','Calculate 1 million digits ↗')
html=html.replace('Accelerated by <a href="https://www.numberworld.org/y-cruncher/" target="_blank" rel="noopener">y-cruncher by Alexander J. Yee</a>. ',
 'This standalone HTML runs entirely in your browser, with five million verified digits embedded. ')
html=html.replace('Automatic measures free RAM before a run. Calculations that fit use RAM; larger ones process bounded arithmetic blocks through temporary disk files. Windows asks to approve only the calculator worker for disk mode. Scratch files are cleared after use, and the new dataset appears after the complete output is verified. Newly generated caches share a 2 GiB budget; imported files and the active dataset are protected.',
 'Five million verified decimal places are bundled. New calculations use exact BigInt Chudnovsky binary splitting in a separate Web Worker. There is no preset application digit ceiling; browser memory, string capacity and storage still apply. Use the desktop native engine for large runs. Imported files are prefix-checked. Computed and imported data are saved in browser storage when available.')
html=html.replace('Native bitset intersections','Browser bitset intersections')
html=html.replace('Quit local engine','Restore bundled digits')
addon="""
document.getElementById('quitBtn').onclick=async()=>{try{await api('restore',{});state.shuttingDown=false;await pollStatus();document.getElementById('guideDialog').close();toast('Restored the bundled five million digits.');}catch(error){toast(error.message);}};
"""
def safe(source):return source.replace('</script','<\\/script')
bundle='<script>window.PI_BUNDLED_DIGITS='+json.dumps(digits)+';</script>\n'
bundle+='<script id="pi-worker-source" type="text/plain">'+safe(engine)+'</script>\n'
bundle+='<script>'+safe(bridge)+'</script>\n<script>'+safe(script)+'\n'+addon+'</script>'
html=html.replace('<script src="app.js"></script>',bundle)
html=html.replace('<script src="viewport.js"></script>','')
html=html.replace('<script src="compute-live.js"></script>','')
html+='\n<!-- Embedded JetBrains Mono font license:\n'+(ROOT/'app/fonts/OFL.txt').read_text(encoding='utf-8').replace('--','—')+'\n-->\n'
target=OUT/'index.html'
target.write_text(html,encoding='utf-8')
readme='''PI EXPLORER — STANDALONE HTML

Open index.html directly in a modern Edge, Chrome, Firefox, or Safari browser.
To publish, upload index.html to any static host that permits JavaScript and
blob Web Workers. No Python, local server, npm install, accounts, or API keys.
The single file includes all JavaScript, CSS, font data and 5 million digits.

Features: the same pan/zoom canvas, digits/text/color/pixel views, number and
word search, variable-width shape search, image import, SFX, statistics,
bookmarks, PNG capture, and digit-file import/export.

The HTML version calculates decimal places with exact BigInt Chudnovsky in a
Web Worker. No preset application digit ceiling is enforced. Browser memory,
exact number representation, string capacity and storage remain real limits.
The included 5 million can be searched immediately. Use the desktop native
engine for large runs; the browser engine does not support disk-backed math.
It cannot run Windows y-cruncher, GMP, or MPFR executables. Native desktop
computation remains faster. Browser speed varies with hardware and browser.

The app saves preferences and the last dataset in browser storage when that
storage is available. Blocking storage does not block computation or search.
Field guide / Restore bundled digits returns to the included 5 million.

A host or HTML embed service must allow scripts and blob workers. Sites that
strip scripts cannot run an interactive app. Standard static hosting works.

Inspired by Nateate's video: https://www.youtube.com/watch?v=wxBWOvELdgk
JetBrains Mono is embedded under the SIL Open Font License, included in the
HTML source and the accompanying OFL.txt. Pi's normality remains unproved.
'''
(OUT/'READ ME.txt').write_text(readme,encoding='utf-8')
(OUT/'OFL.txt').write_bytes((ROOT/'app/fonts/OFL.txt').read_bytes())
with zipfile.ZipFile(ROOT/'Pi Explorer - Static Website.zip','w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
 for f in OUT.iterdir():
  if f.is_file():z.write(f,f.name)
print(json.dumps({'html':str(target),'bytes':target.stat().st_size,'zip':str(ROOT/'Pi Explorer - Static Website.zip')}))
