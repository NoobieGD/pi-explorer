"""Inspect native status bytes using a small fresh RAM-only calculation."""
import sys,time,threading,subprocess,secrets
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import engine,native_runner,resource_plan
count=25_000_000;plan=engine.computation_plan(count,ROOT/'data','ycruncher','ram')
work=ROOT/'data/native-output'/f'run-{count}-{secrets.token_hex(4)}';work.mkdir(parents=True)
command=native_runner.command_for(engine.YCRUNCHER,work,count,{},plan)
command[command.index('status:none')]='status:overwrite';command.insert(1,'console:linux-vterm')
process=subprocess.Popen(command,cwd=work,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
chunks=[]
def read():
    while data:=process.stdout.read1(8192):chunks.append(data)
reader=threading.Thread(target=read);reader.start();started=time.monotonic()
while process.poll() is None:
    log=work/'console.log'
    if (log.exists() and 'Spot Check: Good through' in log.read_text(errors='replace')) or time.monotonic()-started>30:
        native_runner.stop_native(process);break
    time.sleep(.1)
process.wait();reader.join(timeout=3)
raw=b''.join(chunks);(work/'status-probe.bin').write_bytes(raw)
print(repr(raw[-11000:]));print('PROBE',str(work),'BYTES',len(raw))
resource_plan.cleanup(work,ROOT/'data/native-output',True)
