"""Fresh verified A/B disk tuning, then an honest 30-second billion-digit attempt."""
import sys,os,time,json,secrets,re,statistics,platform
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import engine,resource_plan,native_runner
from storage import atomic_write
from digit_store import DigitStore

def job(count,label,options,deadline,memory=128,mode='disk'):
    root=ROOT/'data/native-output';work=root/f'run-{count}-{secrets.token_hex(4)}';work.mkdir(parents=True)
    plan=engine.computation_plan(count,ROOT/'data','ycruncher',mode,memory)
    item={'digits':count,'label':label,'ownerPid':os.getpid(),'plan':plan,'options':options,'deadline':deadline}
    atomic_write(work/'job.json',json.dumps({'owner':'Pi Explorer scratch v1','ownerPid':os.getpid()}));atomic_write(work/'request.json',json.dumps(item));return work

def main():
    candidates=[('legacy-HD',{'ioProfile':'legacy'}),('SSD-all',{'ioProfile':'ssd'})]
    # These sets come from this machine's native topology; no system affinity changes.
    if os.cpu_count()==8 and platform.processor().startswith('Intel64 Family 6 Model 186'):
        candidates += [('SSD-P-cores',{'ioProfile':'ssd','cores':'0-3','tasks':4}),('SSD-physical',{'ioProfile':'ssd','cores':'0,2,4,5,6,7','tasks':6})]
    jobs=[]
    for repeat in range(2):
        for label,options in candidates:jobs.append(job(25_000_000,label,options,90))
    # Small-run CPU affinity results do not establish the fastest billion-digit
    # configuration. Keep native scheduling for the large target attempt.
    jobs.append(job(1_000_000_000,'one-billion-30-seconds',{'ioProfile':'ssd'},30,memory=0,mode='auto'))
    batch=job(1,'benchmark-batch',{},180)
    atomic_write(batch/'request.json',json.dumps({'ownerPid':os.getpid(),'jobs':[str(p/'request.json') for p in jobs]}))
    print('One Windows calculator approval covers this bounded benchmark batch.',flush=True)
    print(f'{len(jobs)-1} fresh 25M calculations at 128 MiB, followed by a fresh 1B attempt with a 30-second deadline.',flush=True)
    process=native_runner.launch(batch/'request.json',elevate=os.name=='nt' and not __import__('ctypes').windll.shell32.IsUserAnAdmin())
    seen=''
    try:
        while process.poll() is None:
            try:
                state=json.loads((batch/'batch-progress.json').read_text());message=f"{state['index']+1}/{state['total']}: {state['label']}"
                if message!=seen:print(message,flush=True);seen=message
            except (OSError,ValueError):pass
            time.sleep(.3)
    except KeyboardInterrupt:(batch/'cancel').touch();raise
    finally:
        if isinstance(process,native_runner.ElevatedProcess):process.close()
    results=[];reference=DigitStore(ROOT/'data/pi-200000000.txt')
    try:
        for work in jobs:
            request=json.loads((work/'request.json').read_text());outcome=json.loads((work/'runner-result.json').read_text()) if (work/'runner-result.json').exists() else {'status':'not_run'}
            log=(work/'console.log').read_text(errors='replace') if (work/'console.log').exists() else ''
            timing=re.search(r'Total Computation Time:\s+([\d.]+)',log)
            row={'name':request['label'],'digits':request['digits'],'cold':True,'options':request['options'],'resourcePlan':request['plan'],**outcome,'nativeSeconds':float(timing[1]) if timing else None,'log':str(work/'console.log')}
            if row['status']=='completed':
                path=next(work.glob('*Dec*.txt'));computed=DigitStore(path)
                try:
                    assert len(computed)==request['digits']
                    compared=min(len(reference),len(computed))
                    assert all(computed[i:min(compared,i+4194304)]==reference[i:min(compared,i+4194304)] for i in range(0,compared,4194304))
                    row.update(comparisonDigits=compared,comparisonPassed=True)
                finally:computed.close()
            resource_plan.cleanup(work,ROOT/'data/native-output',remove_output=True);row['scratchRemoved']=not (work/'swap').exists();results.append(row)
    finally:reference.close()
    medians={name:statistics.median(r['nativeSeconds'] for r in results if r['name']==name and r['status']=='completed') for name,_ in candidates if any(r['name']==name and r['status']=='completed' for r in results)}
    wall_medians={name:statistics.median(r['wallSeconds'] for r in results if r['name']==name and r['status']=='completed') for name in medians}
    supported={name:options for name,options in candidates if name.startswith('SSD') and name in medians}
    best=min(supported,key=lambda name:wall_medians[name]) if supported else None
    if best and 'SSD-all' in medians and wall_medians[best]>=wall_medians['SSD-all']*.95:best='SSD-all'
    if best:atomic_write(ROOT/'data/performance-profile.json',json.dumps({'disk':supported[best],'ram':{},'tunedThroughDigits':25_000_000,'cpuSignature':{'processor':platform.processor(),'logicalCores':os.cpu_count()}}))
    target=results[-1];report={'runs':results,'medianNativeSeconds':medians,'medianVerifiedWallSeconds':wall_medians,'selectedDiskProfile':best,'targetDigits':1_000_000_000,'targetSeconds':30,'targetMet':False,'nativeDeadlineMet':target['status']=='completed' and target.get('wallSeconds',1e9)<30,'targetAttempt':target,'scope':'Native calculation, decimal output, verification and scratch cleanup. Full app ready time is not measured by this tuner.'}
    atomic_write(ROOT/'benchmarks/fastest-native.json',json.dumps(report,indent=2));print(json.dumps({'medians':medians,'selected':best,'billionAttempt':target['status'],'targetMet':report['targetMet']},indent=2),flush=True)

if __name__=='__main__':main()
