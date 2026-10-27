"""Small, bounded probe of the bundled native disk backend."""
import sys,time,subprocess,json,ctypes
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import engine
work=ROOT/'data/native-output/swap-probe';work.mkdir(parents=True,exist_ok=True)
swap=work/'swap';swap.mkdir(exist_ok=True)
if ctypes.windll.shell32.IsUserAnAdmin():raise RuntimeError('This planning-only probe must run without elevation.')
count=int(sys.argv[1]) if len(sys.argv)>1 else 100000
command=[str(engine.YCRUNCHER),'skip-warnings','pause:-2','colors:0','status:none','priority:0','PII:-1','logfile:'+str(work/'console.log'),'custom','pi',f'-dec:{count}','-hex:0','-od:1','-C:0','-verify:1','-mode:swap','-M:134217728','-minIO:256k','-swap:raid0',str(swap)]
with (work/'stdout.log').open('w') as out:
    process=subprocess.Popen(command,cwd=work,stdout=out,stderr=out,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    try:process.wait(timeout=20)
    except subprocess.TimeoutExpired:engine.stop_native(process)
text=(work/'stdout.log').read_text(errors='replace');print(text[text.find('Custom Compute a Constant'):])
print(json.dumps({'exit':process.poll(),'files':[p.name for p in work.iterdir()]}))
