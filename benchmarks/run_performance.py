"""Cold native calculations, bounded-memory view timings, and target feasibility."""
import sys,time,json,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import engine
from digit_store import DigitStore

def median(operation,n=15):
    values=[]
    for _ in range(n):
        t=time.perf_counter();operation();values.append(time.perf_counter()-t)
    return statistics.median(values)

def main():
    report={'cpu':'Intel Core 3 100U','availableRamBytes':engine.available_memory(),'nativeRuns':[],'oneBillionTargetSeconds':60}
    raw=(ROOT/'data/pi-5000000.txt').read_bytes()
    report['vectorizedWhole5MTextSeconds']=median(lambda:engine.letters(raw),5)
    mapped=DigitStore(ROOT/'data/pi-60000000.txt')
    report['tileTextSeconds']=median(lambda:mapped.tile(200,125000,0,70,200,mode='text'))
    report['tileColorSeconds']=median(lambda:mapped.tile(200,125000,0,70,200,mode='colors'))
    report['tilePixelsSeconds']=median(lambda:mapped.tile(200,125000,0,70,200,mode='binary'))
    report['mappingOpenSeconds']=median(lambda:DigitStore(ROOT/'data/pi-60000000.txt').close())
    mapped.close()
    for name,options in [('all-logical',{}),('physical-cores',{'noSMT':True}),('four-tasks',{'tasks':4})]:
        started=time.perf_counter()
        try:
            output,info=engine.compute_ycruncher_file(25000000,ROOT/'data',options=options,deadline=90)
            check=DigitStore(output);assert len(check)==25000000;check.close()
            row={'name':name,'cold':True,'digits':25000000,'wallSeconds':time.perf_counter()-started,**info};report['nativeRuns'].append(row)
            print(json.dumps(row),flush=True)
        except Exception as e:report['nativeRuns'].append({'name':name,'error':str(e)})
        (ROOT/'benchmarks/performance.json').write_text(json.dumps(report,indent=2))
    good=[r for r in report['nativeRuns'] if 'wallSeconds' in r]
    if good:
        best=min(good,key=lambda r:r.get('nativeSeconds') or r['wallSeconds'])
        (ROOT/'data/performance-profile.json').write_text(json.dumps(best['options']))
        report['selectedProfile']=best['name']
    try:
        memory=engine.check_native_memory(1000000000);report['oneBillionMemory']=memory
        started=time.perf_counter();output,info=engine.compute_ycruncher_file(1000000000,ROOT/'data',options=best['options'] if good else {},deadline=60)
        report['oneBillion']={'status':'completed','wallSeconds':time.perf_counter()-started,**info}
    except MemoryError as e:report['oneBillion']={'status':'insufficient_free_memory','error':str(e),'estimatedBytes':engine.native_memory_estimate(1000000000),'availableBytes':engine.available_memory()}
    except TimeoutError as e:report['oneBillion']={'status':'exceeded_60_seconds','error':str(e)}
    except Exception as e:report['oneBillion']={'status':'failed','error':str(e)}
    (ROOT/'benchmarks/performance.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
