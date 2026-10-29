"""Benchmark searches of EXISTING digits only. Never calculates new pi digits.

Full scans, capped scans and exact cache hits are explicitly distinguished.
Use --quick for one thread-count sweep. Results include real wall time.
"""
import sys,time,json,argparse,statistics
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from digit_store import DigitStore
import fast_search,stream_search

def run():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--quick',action='store_true');args=parser.parse_args()
    candidates=[p for suffix in ('txt','ycd','mpt') for p in (ROOT/'data').glob('pi-*.'+suffix)]
    if not candidates:raise SystemExit('No existing pi dataset found. Compute or import digits first, then run Benchmark Scanning.cmd. This benchmark does not generate digits.')
    path=max(candidates,key=lambda p:p.stat().st_size)
    store=DigitStore(path)
    if len(store)<100:store.close();raise SystemExit('Scanning benchmark needs at least 100 existing pi digits.')
    report={'digits':len(store),'file':str(path),'features':fast_search.features(),'runs':[]}
    cases=[('digits','mod26',0,store[len(store)-81:len(store)-57]),
           ('text','mod26',0,store.window(store.total_units('text','mod26')-30,14,'text','mod26')[0]),
           ('text','ascii',1,b'PiExplorer!')]
    try:
        for mode,scheme,alignment,q in cases:
            started=time.perf_counter()
            with patch('fast_search.available',return_value=False):expected=stream_search.search_sequence(store,q,mode,scheme,alignment)
            baseline=time.perf_counter()-started
            entry={'mode':mode,'scheme':scheme,'query':q.decode(),'baselineSeconds':baseline,'matches':len(expected[0]),'trials':[]}
            for threads in (1,2,4,6,8):
                for trial in range(1 if args.quick else 3):
                    info={};started=time.perf_counter();found=fast_search.sequence(store,q,mode,scheme,alignment,metrics=info,threads=threads,use_cache=False);seconds=time.perf_counter()-started
                    assert found[:2]==expected[:2],(mode,scheme,found[:2],expected[:2])
                    value={'threads':threads,'seconds':seconds,'speedup':baseline/seconds,'billionSourceDigitsPerSecond':info['sourceDigits']/seconds/1e9,'complete':not found[1],**info}
                    entry['trials'].append(value);print(mode,scheme,threads,round(seconds,6),round(value['billionSourceDigitsPerSecond'],3),'billion/s',flush=True)
            fast_search.sequence(store,q,mode,scheme,alignment)
            info={};started=time.perf_counter();fast_search.sequence(store,q,mode,scheme,alignment,metrics=info);entry['exactCacheSeconds']=time.perf_counter()-started
            report['runs'].append(entry)
        target=ROOT/'benchmarks/scan-speed.json';target.write_text(json.dumps(report,indent=2));print('Report:',target,flush=True)
    finally:store.close()

if __name__=='__main__':run()
