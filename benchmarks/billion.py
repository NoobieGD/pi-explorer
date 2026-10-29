"""An independent, fresh, verified billion-digit benchmark; Codex is not needed."""
import time,sys,json,subprocess,os,argparse,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import engine

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--check',action='store_true');parser.add_argument('--timeout',type=int,default=600);parser.add_argument('--target-seconds',type=int,default=30);args=parser.parse_args()
    if args.target_seconds<1:parser.error('--target-seconds must be positive')
    print('PI EXPLORER / 1,000,000,000 DIGITS / FRESH VERIFIED COMPUTATION',flush=True)
    print('Cached digits are never used as the benchmark result.',flush=True)
    record={'digits':1000000000,'cold':True,'targetSeconds':args.target_seconds,'verification':True}
    (ROOT/'data').mkdir(exist_ok=True)
    try:
        from native_install import require_native
        require_native(engine.YCRUNCHER)
        memory=engine.computation_plan(1000000000,ROOT/'data',method='ycruncher');record['memory']=memory
        print(f"Mode: {memory['mode']}. Available RAM: {memory['availableBytes']/2**30:.2f} GiB. Working budget: {memory['ramBudgetBytes']/2**20:.0f} MiB. Peak disk cap: {memory['peakDiskBytes']/2**30:.2f} GiB.",flush=True)
        if memory['requiresElevation']:print('Disk-backed blocks require the Windows administrator prompt for the calculator worker.',flush=True)
    except (MemoryError,OSError,ValueError) as error:
        record.update(status='resource_check_failed',targetVerified=False,error=str(error));print(str(error),flush=True)
        (ROOT/'benchmarks/billion-latest.json').write_text(json.dumps(record,indent=2));return 2
    if args.check:print('Memory check passed; no calculation requested.');return 0
    progress=ROOT/'data'/f'billion-benchmark-{uuid.uuid4().hex}.json'
    started=time.perf_counter();flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
    process=subprocess.Popen([sys.executable,str(ROOT/'engine.py'),'1000000000','ycruncher',str(ROOT/'data'),progress.name],cwd=ROOT,creationflags=flags,env={**os.environ,'PYTHONUTF8':'1'})
    last=''
    while process.poll() is None:
        elapsed=time.perf_counter()-started
        try:
            state=json.loads(progress.read_text());message=state.get('message','Starting native engine')
            if state.get('nativeJob'):
                live=json.loads((ROOT/'data/native-output'/state['nativeJob']/'telemetry.json').read_text())
                message=live['phaseLabel']+(f" {live['phaseProgress']*100:.0f}%" if live.get('phaseProgress') is not None else '')
        except (OSError,ValueError):message='Starting native engine'
        line=f'{elapsed:7.1f}s / {message}'
        if message!=last:print(line,flush=True);last=message
        if elapsed>args.timeout:
            engine.stop_native(process);record.update(status='timed_out',wallSeconds=elapsed,targetVerified=False);break
        time.sleep(.2)
    else:
        elapsed=time.perf_counter()-started
        if process.returncode==0:
            record.update(status='completed',wallSeconds=elapsed,targetVerified=elapsed<args.target_seconds,metadata=json.loads((ROOT/'data/pi-1000000000.json').read_text()))
            print(f'Fresh computation, verification and cache commit: {elapsed:.3f}s. Under {args.target_seconds} seconds: {elapsed<args.target_seconds}.',flush=True)
        else:record.update(status='failed',exitCode=process.returncode,targetVerified=False,wallSeconds=elapsed)
    (ROOT/'benchmarks/billion-latest.json').write_text(json.dumps(record,indent=2))
    return 0 if record['status']=='completed' else 1

if __name__=='__main__':raise SystemExit(main())
