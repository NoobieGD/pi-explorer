"""Measure independent full queries in the actual running desktop backend.
Reads existing digits only; never changes the dataset or calculates pi.
"""
import sys,json,time,statistics,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from digit_store import DigitStore
BASE='http://127.0.0.1:31415/api/'
def get(path):return json.load(urllib.request.urlopen(BASE+path))
def run():
    status=get('status');source=ROOT/'data'/f"pi-{status['count']}.txt";store=DigitStore(source)
    report={'digits':len(store),'health':get('health'),'runs':[]}
    def search(payload):
        req=urllib.request.Request(BASE+'search',json.dumps(payload).encode(),{'Content-Type':'application/json','X-Pi-Token':status['token']})
        task=json.load(urllib.request.urlopen(req))
        while True:
            job=get('job/'+task['id'])
            if job['status']!='running':break
            time.sleep(.008)
        assert job['status']=='done',job
        return job
    try:
        for mode,scheme in [('digits','mod26'),('text','mod26'),('text','ascii')]:
            trials=[]
            for i in range(5):
                q=store[len(store)-100-3*i:len(store)-76-3*i].decode() if mode=='digits' else store.window(store.total_units('text',scheme)-40-i,14,'text',scheme)[0].decode() if scheme=='mod26' else 'PiExplorer!'+chr(65+i)
                payload={'mode':mode,'scheme':scheme,'query':q}
                job=search(payload)
                assert not job['scan']['cacheHit'] and not job['capped'] and job['scan']['sourceDigits']>=len(store)-2
                for match in job['matches']:assert store.window(match['index'],len(q),mode,scheme)[0].decode()==q
                trials.append({'query':q,**{key:job[key] for key in ('seconds','digitsPerSecond','scan')}})
            cached=search(payload);assert cached['scan']['cacheHit'] and 'digitsPerSecond' not in cached
            entry={'mode':mode,'scheme':scheme,'medianSeconds':statistics.median(t['seconds'] for t in trials),'trials':trials,'cachedSeconds':cached['seconds']}
            report['runs'].append(entry);print(mode,scheme,entry['medianSeconds'],'seconds',flush=True)
        (ROOT/'benchmarks/scan-live.json').write_text(json.dumps(report,indent=2))
    finally:store.close()
if __name__=='__main__':run()
