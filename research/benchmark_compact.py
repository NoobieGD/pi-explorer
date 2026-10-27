"""Bounded compact-math experiment. Never computes 200B digits."""
import json,sys,time,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'research'))
import compact_engine as compact
import engine
import fast_search
from digit_store import DigitStore

def run():
    fast_search._performance_worker()  # Tag this performance-critical benchmark thread HighQoS.
    store=DigitStore(max((ROOT/'data').glob('pi-*.txt'),key=lambda p:p.stat().st_size))
    report={'prototype':'exact cross-factor cancellation','largeRunStarted':False,'cases':[]}
    try:
        for count in (100_000,500_000,1_000_000,5_000_000):
            case={'digits':count,'trials':[]}
            for trial in range(3):
                for cancel in ((False,True) if trial%2==0 else (True,False)):
                    result,stats=compact.compute(count,cancel=cancel,inspect=trial==0)
                    assert result.encode()==store[:count]
                    case['trials'].append(stats);print(count,stats['method'],round(stats['seconds'],3),'seconds',stats['rootPayloadBytes'],'root bytes',flush=True)
            plain=[t for t in case['trials'] if t['method']=='exact-standard'];compact_trials=[t for t in case['trials'] if t['method']=='exact-cancelled']
            case.update(standardMedianSeconds=statistics.median(t['seconds'] for t in plain),compactMedianSeconds=statistics.median(t['seconds'] for t in compact_trials),rootReduction=1-compact_trials[0]['rootPayloadBytes']/plain[0]['rootPayloadBytes'])
            case['timeRatio']=case['compactMedianSeconds']/case['standardMedianSeconds']
            report['cases'].append(case)
        # One fresh 5M native RAM run; wall and reported computation are separate.
        native_started=time.perf_counter()
        path,info=engine.compute_ycruncher_file(5_000_000,ROOT/'data',options={'storageMode':'ram'},deadline=90)
        native_store=DigitStore(path)
        try:assert native_store[:5_000_000]==store[:5_000_000]
        finally:native_store.close()
        report['native5M']={'endToEndSeconds':time.perf_counter()-native_started,**info}
        engine.resource_plan.cleanup(path.parent,ROOT/'data/native-output',remove_output=True)
        report['targetPlan']=compact.plan(200_000_000_000)
        (ROOT/'benchmarks/compact-research.json').write_text(json.dumps(report,indent=2))
    finally:store.close()
if __name__=='__main__':run()
