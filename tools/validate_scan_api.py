"""Verify the fast search HTTP path using existing digits on an ephemeral port.
No pi computation or active-dataset change. Writes only its benchmark report.
"""
import sys,json,time,threading,urllib.request,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import server,fast_search

def run():
    source=max((ROOT/'data').glob('pi-*.txt'),key=lambda p:p.stat().st_size)
    server.load_file(source);store=server.DIGITS
    http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
    thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{http.server_port}/api/'
    def get(path):return json.load(urllib.request.urlopen(base+path))
    def search(payload):
        request=urllib.request.Request(base+'search',json.dumps(payload).encode(),{'Content-Type':'application/json','X-Pi-Token':server.TOKEN})
        job=json.load(urllib.request.urlopen(request));started=time.perf_counter()
        while True:
            result=get('job/'+job['id'])
            if result['status']!='running':break
            time.sleep(.008)
        assert result['status']=='done',result
        result['clientWaitSeconds']=time.perf_counter()-started;return result
    report={'digits':len(store),'file':str(source),'health':get('health'),'fullScans':[]}
    try:
        cases=[{'mode':'digits','query':store[len(store)-81:len(store)-57].decode()},
               {'mode':'text','scheme':'mod26','query':store.window(store.total_units('text','mod26')-30,14,'text','mod26')[0].decode()},
               {'mode':'text','scheme':'ascii','alignment':1,'query':'PiExplorer!'}]
        for payload in cases:
            trials=[]
            for i in range(5):
                fast_search.clear_cache();job=search(payload)
                assert not job['capped'] and not job['scan']['cacheHit']
                assert job['scan']['sourceDigits']>=len(store)-2
                for match in job['matches']:
                    mode=payload['mode'];scheme=payload.get('scheme','mod26');alignment=payload.get('alignment',0)
                    value=store.window(match['index'],len(payload['query']),mode,scheme,alignment=alignment)[0].decode()
                    assert value==payload['query'],(value,payload)
                trials.append({key:job[key] for key in ('seconds','digitsPerSecond','clientWaitSeconds','scanned','scan')})
            cached=search(payload);assert cached['scan']['cacheHit'] and 'digitsPerSecond' not in cached
            value={'payload':payload,'matches':len(job['matches']),'trials':trials,'medianSeconds':statistics.median(t['seconds'] for t in trials),'cachedSeconds':cached['seconds']}
            report['fullScans'].append(value);print(payload['mode'],payload.get('scheme'),value['medianSeconds'],'seconds',flush=True)
        capped=search({'mode':'digits','query':'12345'})
        assert capped['capped'] and len(capped['matches'])==300 and capped['scanned']<len(store)
        assert capped['matches'][0]['position']==49702 and 'digitsPerSecond' not in capped
        video=search({'mode':'text','scheme':'mod26','query':'PIE'})
        assert video['matches'][0]['unitPosition']==10962
        rows=['11111','01010','01010','01010','01011']
        shape=search({'mode':'shape','rows':rows,'sweep':True,'minWidth':6,'maxWidth':320})
        for match in shape['matches']:
            for y,row in enumerate(rows):assert store.window(match['index']+y*match['width'],len(row),'binary')[0]==row.encode()
        report['cappedScan']={k:capped[k] for k in ('seconds','scanned','scan')}
        report['pixelSweep']={k:shape[k] for k in ('seconds','scanned','scan')};report['checks']='All existing-data API checks passed'
        (ROOT/'benchmarks/scan-api.json').write_text(json.dumps(report,indent=2))
        print(report['checks'],flush=True)
    finally:
        http.shutdown();http.server_close();thread.join();server.POOL.shutdown(wait=True);store.close()

if __name__=='__main__':run()
