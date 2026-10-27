"""Real local HTTP compute/search/cache smoke test with an isolated dataset."""
import sys, tempfile, threading, time, json, urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import server

def main():
    with tempfile.TemporaryDirectory(prefix='pi-tachuspi-api-') as directory:
        server.DATA=Path(directory)
        service=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{service.server_port}/api/'
        def request(path,body=None):
            req=urllib.request.Request(base+path,data=None if body is None else json.dumps(body).encode(),
                headers={'Content-Type':'application/json','X-Pi-Token':server.TOKEN})
            with urllib.request.urlopen(req,timeout=5) as response:return json.load(response)
        def finish():
            end=time.monotonic()+20;saw_telemetry=False
            while time.monotonic()<end:
                state=request('status');saw_telemetry |= bool(state.get('telemetry'))
                if not state.get('busy'):
                    assert not state.get('error'),state.get('error')
                    return state,saw_telemetry
                time.sleep(.05)
            raise TimeoutError('Isolated API computation did not finish')
        try:
            plan=request('plan?count=62831853071&method=tachuspi&storageMode=disk&force=true')
            assert plan['launchable'] and not plan['storageBoundVerified']
            payload={'method':'tachuspi','count':'1000000','storageMode':'disk','memoryMiB':32}
            request('compute',payload);state,telemetry=finish()
            assert state['method']=='tachuspi' and state['count']==1_000_000
            assert telemetry,'Native live telemetry must reach the HTTP API'
            data=request('digits?start=0&count=50')['data']
            assert data.startswith('14159265358979323846264338327950288419716939937510')
            job=request('search',{'mode':'digits','query':'12345'})['id']
            end=time.monotonic()+10
            while time.monotonic()<end:
                search=request('job/'+job)
                if search['status']!='running':break
                time.sleep(.05)
            assert search['status']=='done',search
            assert search['matches'][0]['position']==49702,search['matches'][:1]
            cached=server.DATA/'pi-1000000.mpt';stamp=cached.stat().st_mtime_ns
            request('compute',payload);state,_=finish()
            assert state['cacheHit'] and cached.stat().st_mtime_ns==stamp
            report={'verified':True,'count':1_000_000,'computeEndpoint':True,
                    'packedDigitsEndpoint':True,'searchEndpoint':True,'cacheReuse':True,
                    'telemetryObserved':telemetry,'largeTargetPlanOnly':plan,
                    'largeTargetComputed':False}
            (ROOT/'benchmarks/tachuspi-api-validation.json').write_text(json.dumps(report,indent=2))
            print(json.dumps({k:v for k,v in report.items() if k!='largeTargetPlanOnly'},indent=2))
        finally:
            service.shutdown();service.server_close();thread.join()
            if hasattr(server.DIGITS,'close'):server.DIGITS.close()

if __name__=='__main__':main()
