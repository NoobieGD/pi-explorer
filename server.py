"""Local-only desktop application server. No cloud, accounts, or telemetry."""
import sys, os, json, time, threading, subprocess, secrets, traceback, webbrowser, hashlib
from pathlib import Path
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
from concurrent.futures import ThreadPoolExecutor
from collections import OrderedDict
from storage import atomic_write
import engine
from digit_store import DigitStore,unit_step
import numpy as np
from stream_search import search_sequence,search_shapes
import fast_search
from constants import identify,CONSTANTS,infer

ROOT=Path(__file__).resolve().parent
DATA=ROOT/'data'; DATA.mkdir(exist_ok=True)
INSTALLATION_ID=hashlib.sha256(str(ROOT.resolve()).casefold().encode()).hexdigest()[:20]
TOKEN=secrets.token_urlsafe(24)
LOCK=threading.RLock()
POOL=ThreadPoolExecutor(max_workers=2)
STATE={'count':0,'constant':'pi','integerPart':3,'busy':False,'progress':0,'message':'Ready','method':'auto','seconds':0}
DIGITS=b''
DERIVED={}
JOBS=OrderedDict()
PROCESS=None
ACTIVE_CANCEL=None

def load_file(path):
    global DIGITS
    meta=path.with_suffix('.json')
    info=json.loads(meta.read_text()) if meta.exists() else {}
    constant=infer(path,info.get('constant'));value=DigitStore(path,constant=constant)
    with LOCK:
        DIGITS=value;DERIVED.clear();fast_search.clear_cache()
        meta=path.with_suffix('.json')
        info=json.loads(meta.read_text()) if meta.exists() else {}
        STATE.update(count=len(value),constant=constant,integerPart=CONSTANTS[constant]['integer'],datasetId=value.version,seconds=info.get('seconds',0),nativeSeconds=info.get('nativeSeconds'),method=info.get('method','imported'),
                     message='Ready to explore',progress=1,resourcePlan=info.get('resourcePlan'))
    atomic_write(DATA/'active-dataset.json',json.dumps({'file':path.name,'constant':constant}))

def compute_job(count,method,force=False,settings=None):
    global PROCESS,ACTIVE_CANCEL
    try:
        constant=identify((settings or {}).get('constant','pi'))
        path=engine.resource_plan.dataset_path(DATA,count,'mpt' if method=='tachuspi' else method=='ycruncher-low',constant=constant)
        meta=path.with_suffix('.json')
        cached_method=json.loads(meta.read_text()).get('method') if meta.exists() else ''
        if path.exists() and not force and (method=='auto' or cached_method==method):
            started=time.perf_counter()
            load_file(path)
            with LOCK: STATE.update(busy=False,message='Loaded cached digits · not a new computation',cacheHit=True,operationSeconds=time.perf_counter()-started)
            return
        progress_file=DATA/f'compute-progress-{secrets.token_hex(6)}.json'
        request_file=progress_file.with_suffix('.request.json')
        atomic_write(request_file,json.dumps(settings or {}))
        with LOCK:ACTIVE_CANCEL=progress_file.with_suffix('.cancel')
        cmd=[sys.executable,str(ROOT/'engine.py'),str(count),method,str(DATA),progress_file.name,request_file.name]
        flags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0
        p=subprocess.Popen(cmd,creationflags=flags,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,env={**os.environ,'PYTHONUTF8':'1'})
        with LOCK: PROCESS=p
        with LOCK:
            if STATE.get('cancelled'):ACTIVE_CANCEL.touch()
        progress_stamp=None
        stderr_tail=bytearray()
        def drain_errors():
            while chunk:=p.stderr.read(4096):
                stderr_tail.extend(chunk)
                if len(stderr_tail)>65536:del stderr_tail[:-65536]
        error_reader=threading.Thread(target=drain_errors,daemon=True);error_reader.start()
        while p.poll() is None:
            f=progress_file
            try:
                stamp=f.stat().st_mtime_ns
                if stamp!=progress_stamp:
                    info=json.loads(f.read_text())
                    with LOCK: STATE.update(info)
                    progress_stamp=stamp
            except (OSError,ValueError): pass
            time.sleep(.15)
        error_reader.join(timeout=3)
        p.stderr.close()
        code=p.returncode
        if code==0:
            path=engine.resource_plan.dataset_path(DATA,count,'mpt' if method=='tachuspi' else method=='ycruncher-low',constant=constant)
            try:
                committed=json.loads(progress_file.read_text()).get('datasetFile')
                if committed in {f'{constant}-{count}.{suffix}' for suffix in ('txt','ycd','mpt')} and (DATA/committed).is_file():path=DATA/committed
            except (OSError,ValueError):pass
            load_file(path)
            with LOCK: STATE.update(busy=False,error=None,cacheHit=False,operationSeconds=STATE['seconds'])
        else:
            err=stderr_tail.decode(errors='replace')[-4000:]
            atomic_write(DATA/'last-computation-error.log',err or 'Computation failed without diagnostic output')
            with LOCK:
                if STATE.get('cancelled'): STATE.update(busy=False,message='Computation cancelled',progress=0)
                else: STATE.update(busy=False,error=err or 'Computation failed',message='Computation failed: '+(err.splitlines()[-1] if err else 'see data/last-computation-error.log'))
    except Exception as e:
        with LOCK: STATE.update(busy=False,error=str(e),message='Computation failed: '+str(e))
    finally:
        with LOCK: PROCESS=None;ACTIVE_CANCEL=None
        for temporary in (locals().get('progress_file'),locals().get('request_file')):
            if temporary:
                try:temporary.unlink(missing_ok=True);temporary.with_suffix('.cancel').unlink(missing_ok=True)
                except OSError:pass

def search_job(job,payload):
    try:
        started=time.perf_counter()
        mode=payload.get('mode','digits')
        scheme=payload.get('scheme','mod26');rule=payload.get('rule','threshold')
        alignment=int(payload.get('alignment',0))
        if scheme not in ('mod26','a1z26','ascii'):raise ValueError('Unknown text encoding')
        if mode=='text' and not 0<=alignment<unit_step(mode,scheme):raise ValueError('Invalid text alignment')
        scan_info={}
        with LOCK:store=DIGITS
        cancelled=lambda:job.get('cancel',False)
        if mode=='shape':
            rows=payload['rows']
            width=int(payload.get('width',200))
            if payload.get('sweep'):
                lo=max(len(rows[0]),int(payload.get('minWidth',6)))
                hi=min(1024,int(payload.get('maxWidth',320)))
                widths=range(lo,hi+1)
            else: widths=[width]
            def progress(v,m): job.update(progress=v,message=m)
            matches,capped=search_shapes(store,rows,widths,rule,60,cancelled,progress,scan_info)
            query='/'.join(rows)
        else:
            query=payload.get('query','').strip()
            if mode=='text':
                if not query.isascii(): raise ValueError('Use ASCII text for this encoding')
                if scheme!='ascii': query=query.upper()
            elif not query.isdigit(): raise ValueError('Enter digits 0–9')
            if not query or len(query)>2048: raise ValueError('Enter a pattern of 1–2,048 characters')
            def progress(v,m):job.update(progress=v,message=m)
            positions,capped,conversion_seconds=search_sequence(store,query.encode('ascii'),mode,scheme,alignment,300,cancelled,progress,scan_info)
            job['conversionSeconds']=conversion_seconds
            step=3 if scheme=='ascii' else 2
            matches=[{'index':p,'position':(p*step+alignment+1 if mode=='text' else p+1),
                      'unitPosition':p+1,'length':len(query)} for p in positions]
        seconds=time.perf_counter()-started
        scanned=scan_info.get('scanned',store.total_units('text' if mode=='text' else 'digits',scheme,alignment))
        job.update(status='done',matches=matches,capped=capped,query=query,seconds=seconds,
                   scanned=scanned,scan=scan_info,progress=1,message='Search complete')
        if not scan_info.get('cacheHit') and not capped:
            job['digitsPerSecond']=scan_info.get('sourceDigits',scanned)/max(seconds,1e-9)
    except InterruptedError: job.update(status='cancelled',message='Search cancelled')
    except Exception as e: job.update(status='error',error=str(e))

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    disable_nagle_algorithm=True
    def log_message(self,*a): pass
    def reject_post(self,value,status):
        # Windows can reset a socket closed with unread POST bytes, discarding
        # the session-expired response. Drain small UI commands before closing.
        try:
            length=int(self.headers.get('Content-Length','0'))
            if 0<length<=65536:
                previous=self.connection.gettimeout();self.connection.settimeout(.25)
                try:self.rfile.read(length)
                finally:self.connection.settimeout(previous)
        except (OSError,ValueError):pass
        self.close_connection=True;return self.send(value,status)
    def send(self,value,status=200,kind='application/json'):
        body=json.dumps(value).encode() if kind=='application/json' else value
        self.send_response(status)
        self.send_header('Content-Type',kind)
        self.send_header('Content-Length',str(len(body)))
        self.send_header('Cache-Control','no-store' if kind=='application/json' else 'no-cache')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        if self.close_connection:self.send_header('Connection','close')
        self.end_headers();self.wfile.write(body)
    def do_GET(self):
        parsed=urlparse(self.path);p=parsed.path;qs=parse_qs(parsed.query)
        try:
            if p=='/api/status':
                with LOCK: result=dict(STATE)
                if result.get('busy') and result.get('startedAt'):result['elapsed']=time.perf_counter()-result['startedAt']
                if result.get('busy') and result.get('nativeJob'):
                    try:
                        work=engine.resource_plan.checked_job(DATA/'native-output'/result['nativeJob'],DATA/'native-output')
                        live=json.loads((work/'telemetry.json').read_text(encoding='utf-8'))
                        live['ageSeconds']=max(0,time.time()-live['updatedAt'])
                        result.update(telemetry=live,progress=live['overallEstimate'],message=live['phaseLabel'])
                    except (OSError,ValueError,KeyError):pass
                result.update(constants=[{'id':key,**value} for key,value in CONSTANTS.items()],token=TOKEN,engine=engine.g.mp_version(),maxDigits=engine.MAX_DIGITS,maxInlineImportBytes=max(65536,engine.available_memory()//8))
                return self.send(result)
            if p=='/api/plan':
                count=engine.resource_plan.digit_count(qs.get('count',['5000000'])[0]);method=qs.get('method',['auto'])[0]
                constant=identify(qs.get('constant',['pi'])[0])
                mode=qs.get('storageMode',['auto'])[0];memory=int(qs.get('memoryMiB',['0'])[0]);force=qs.get('force',['false'])[0]=='true'
                if method not in ('auto','ycruncher','ycruncher-low','tachuspi','chudnovsky','exact','mpfr','compact'):raise ValueError('Unknown arithmetic engine')
                if constant!='pi' and method in ('tachuspi','compact'):raise ValueError('This engine supports pi only')
                target=engine.resource_plan.dataset_path(DATA,count,'mpt' if method=='tachuspi' else method=='ycruncher-low',constant=constant);meta=target.with_suffix('.json')
                cached=target.exists() and not force and (method=='auto' or (meta.exists() and json.loads(meta.read_text()).get('method')==method))
                if cached:return self.send({'mode':'cache','digits':count,'ramBudgetBytes':0,'peakDiskBytes':0,'outputBytes':target.stat().st_size,'requiresElevation':False})
                return self.send(engine.computation_plan(count,DATA,method,mode,memory,constant=constant))
            if p=='/api/compact-check':
                from research.compact_engine import plan as compact_plan
                count=engine.resource_plan.digit_count(qs.get('count',['200000000000'])[0])
                return self.send(compact_plan(count))
            if p=='/api/digits':
                start=max(0,int(qs.get('start',['0'])[0]));count=min(2_000_000,max(1,int(qs.get('count',['10000'])[0])))
                mode=qs.get('mode',['digits'])[0]
                with LOCK:store=DIGITS
                if not store:return self.send({'start':start,'total':0,'data':''})
                raw,total=store.window(start,count,mode,qs.get('scheme',['mod26'])[0],qs.get('rule',['threshold'])[0],int(qs.get('alignment',['0'])[0]))
                return self.send({'start':start,'total':total,'data':raw.decode('ascii')})
            if p=='/api/tile':
                q=lambda k,default:int(qs.get(k,[str(default)])[0])
                grid_width=max(4,min(4096,q('gridWidth',200)));rows=max(1,min(2048,q('rows',1)));cols=max(1,min(4096,q('cols',1)))
                if rows*cols>1_000_000:raise ValueError('Tile exceeds one million samples')
                row_start=max(0,q('rowStart',0));col_start=max(0,min(grid_width-1,q('colStart',0)));row_step=max(1,q('rowStep',1));col_step=max(1,q('colStep',1))
                with LOCK:store=DIGITS
                if not store:return self.send({'data':'','total':0,'rows':0,'cols':0})
                started=time.perf_counter();data,total=store.tile(grid_width,row_start,col_start,rows,cols,row_step,col_step,qs.get('mode',['digits'])[0],qs.get('scheme',['mod26'])[0],qs.get('rule',['threshold'])[0],q('alignment',0))
                return self.send({'data':data.decode('ascii'),'total':total,'rows':rows,'cols':cols,'rowStart':row_start,'colStart':col_start,'rowStep':row_step,'colStep':col_step,'conversionSeconds':time.perf_counter()-started})
            if p=='/api/stats': return self.send(engine.statistics(DIGITS))
            if p.startswith('/api/job/'):
                job=JOBS.get(p.split('/')[-1])
                return self.send({k:v for k,v in job.items() if k!='cancel'} if job else {'error':'Search not found'},200 if job else 404)
            if p=='/api/export':
                with LOCK:store=DIGITS
                if not store:return self.send(b'3.',kind='text/plain')
                self.send_response(200);self.send_header('Content-Type','text/plain; charset=utf-8');self.send_header('Content-Disposition',f'attachment; filename="{getattr(store,'constant','pi')}-{len(store)}-decimal-places.txt"');self.send_header('Content-Length',str(len(store)+2));self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(str(getattr(store,'integerPart',3)).encode()+b'.')
                for chunk in store.chunks():self.wfile.write(chunk)
                return
            if p=='/api/health': return self.send({'app':'Pi Explorer','version':'1.1.2','installationId':INSTALLATION_ID,'scanner':fast_search.features()})
            if p=='/favicon.ico': return self.send(b'',kind='image/x-icon')
            file=ROOT/'app'/('index.html' if p=='/' else p.lstrip('/'))
            if not file.resolve().is_relative_to((ROOT/'app').resolve()) or not file.is_file():
                return self.send({'error':'Not found'},404)
            types={'.html':'text/html; charset=utf-8','.js':'text/javascript; charset=utf-8','.css':'text/css; charset=utf-8','.woff2':'font/woff2','.svg':'image/svg+xml','.ico':'image/x-icon','.wav':'audio/wav'}
            return self.send(file.read_bytes(),kind=types.get(file.suffix,'application/octet-stream'))
        except (ValueError,KeyError) as e: self.send({'error':str(e)},400)
        except (BrokenPipeError,ConnectionResetError): pass
        except (MemoryError,OSError) as e: self.send({'error':str(e)},422)
        except Exception as e: self.send({'error':str(e)},500)
    def do_POST(self):
        try:
            origin=self.headers.get('Origin','')
            host=self.headers.get('Host','')
            if origin and origin!=f'http://{host}':
                return self.reject_post({'error':'Local requests only'},403)
            if self.headers.get('X-Pi-Token')!=TOKEN:
                # The request body has not been consumed. Close this connection
                # so its bytes cannot corrupt the following HTTP request.
                return self.reject_post({'error':'Local session changed; reconnecting','code':'SESSION_EXPIRED'},403)
            length=int(self.headers.get('Content-Length','0'))
            if length<0 or length>max(65536,engine.available_memory()//8):
                self.close_connection=True
                return self.send({'error':'This inline upload exceeds the current RAM budget. For large digit files, place pi-<count>.txt in the app data folder and reopen the app.'},413)
            payload=json.loads(self.rfile.read(length) or b'{}')
            if self.path=='/api/compute':
                count=engine.resource_plan.digit_count(payload.get('count',1_000_000));method=payload.get('method','auto')
                constant=identify(payload.get('constant','pi'))
                if method not in ('auto','ycruncher','ycruncher-low','tachuspi','chudnovsky','exact','mpfr','compact'): raise ValueError('Unknown arithmetic engine')
                if constant!='pi' and method in ('tachuspi','compact'):raise ValueError('This engine supports pi only')
                target=engine.resource_plan.dataset_path(DATA,count,'mpt' if method=='tachuspi' else method=='ycruncher-low',constant=constant)
                settings={'constant':constant,'storageMode':payload.get('storageMode','auto'),'memoryMiB':int(payload.get('memoryMiB',0))}
                settings['serverPid']=os.getpid()
                if hasattr(DIGITS,'path'):settings['protectedCache']=DIGITS.path.name
                meta=target.with_suffix('.json')
                cached=target.exists() and not payload.get('force') and (method=='auto' or (meta.exists() and json.loads(meta.read_text()).get('method')==method))
                plan={'mode':'cache'} if cached else engine.computation_plan(count,DATA,method,settings['storageMode'],settings['memoryMiB'],constant=constant)
                if plan.get('launchable') is False:raise MemoryError(plan['message'])
                with LOCK:
                    if STATE['busy']: return self.send({'error':'A computation is already running'},409)
                    STATE.update(busy=True,targetConstant=constant,progress=0,message='Starting compact exact engine' if method=='compact' else 'Starting disk-backed blocks' if plan['mode']=='disk' else 'Starting native engine',error=None,cancelled=False,target=count,startedAt=time.perf_counter(),cacheHit=False,resourcePlan=plan,nativeJob=None,telemetry=None,phaseProgress=None,progressKind=None)
                threading.Thread(target=compute_job,args=(count,method,bool(payload.get('force')),settings),daemon=True).start()
                return self.send({'ok':True})
            if self.path=='/api/cancel':
                with LOCK:
                    STATE['cancelled']=True
                    if ACTIVE_CANCEL:ACTIVE_CANCEL.touch()
                return self.send({'ok':True})
            if self.path=='/api/search':
                if not DIGITS: raise ValueError('Compute or import digits first')
                with LOCK:
                    if sum(j['status']=='running' for j in JOBS.values())>=2: return self.send({'error':'Wait for the current searches'},409)
                    job={'id':secrets.token_hex(6),'status':'running','progress':0,'message':'Preparing search','cancel':False}
                    JOBS[job['id']]=job
                    for key in list(JOBS):
                        if len(JOBS)>24 and JOBS[key]['status']!='running': JOBS.pop(key)
                POOL.submit(search_job,job,payload)
                return self.send({'id':job['id']})
            if self.path=='/api/search/cancel':
                job=JOBS.get(payload.get('id'))
                if job: job['cancel']=True
                return self.send({'ok':True})
            if self.path=='/api/import':
                text=payload.get('digits','').strip()
                constant=identify(payload.get('constant',STATE.get('constant','pi')));spec=CONSTANTS[constant]
                if text.startswith(str(spec['integer'])+'.'): text=text[2:]
                text=''.join(text.split())
                if not text.isascii() or not text.isdigit(): raise ValueError('Import decimal digits of '+spec['label'])
                if len(text)<50 or not text.startswith(spec['prefix']):
                    raise ValueError('The first 50 digits do not match '+spec['label'])
                with LOCK:
                    if STATE['busy']: raise ValueError('Wait for computation before importing')
                    path=DATA/f'{constant}-{len(text)}.txt'
                    if path.exists():
                        previous=DigitStore(path,constant=constant)
                        try:
                            if any(previous[i:i+4*1024*1024]!=text[i:i+4*1024*1024].encode('ascii') for i in range(0,len(text),4*1024*1024)):raise ValueError('This file disagrees with the cached digits')
                        finally:previous.close()
                    else:
                        path.write_text(text,encoding='ascii')
                        path.with_suffix('.json').write_text(json.dumps({'constant':constant,'integerPart':spec['integer'],'method':'imported (prefix checked)','seconds':0}))
                    load_file(path)
                return self.send({'ok':True,'count':len(text)})
            if self.path=='/api/shutdown':
                self.send({'ok':True})
                with LOCK:
                    STATE['cancelled']=True
                    if ACTIVE_CANCEL:ACTIVE_CANCEL.touch()
                def shutdown():
                    if PROCESS and PROCESS.poll() is None:
                        try:PROCESS.wait(timeout=12)
                        except subprocess.TimeoutExpired:stop_process(PROCESS)
                    self.server.shutdown()
                threading.Thread(target=shutdown,daemon=True).start();return
            return self.send({'error':'Unknown command'},404)
        except (ValueError,TypeError,KeyError) as e: self.send({'error':str(e)},400)
        except (BrokenPipeError,ConnectionResetError): pass
        except (MemoryError,OSError) as e: self.send({'error':str(e)},422)
        except Exception as e: self.send({'error':str(e)},500)

def stop_process(process):
    if os.name=='nt':
        subprocess.run(['taskkill','/PID',str(process.pid),'/T','/F'],stdout=subprocess.DEVNULL,
                       stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    else: process.terminate()

def launch_url(url):
    return url+('&' if '?' in url else '?')+'launch='+secrets.token_urlsafe(12)

def open_window(url):
    # A unique navigation reloads a reused Edge app window after engine restart.
    url=launch_url(url)
    # An app window keeps the desktop experience free of browser chrome.
    if os.name=='nt':
        candidates=[Path(os.environ.get('PROGRAMFILES(X86)',''))/'Microsoft/Edge/Application/msedge.exe',
                    Path(os.environ.get('PROGRAMFILES',''))/'Google/Chrome/Application/chrome.exe']
        for exe in candidates:
            if exe.exists():
                subprocess.Popen([str(exe),'--app='+url,'--window-size=1500,960'],creationflags=subprocess.CREATE_NO_WINDOW)
                return
    webbrowser.open(url)

def main():
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('--no-browser',action='store_true');parser.add_argument('--port',type=int,default=31415)
    args=parser.parse_args()
    import urllib.request,socket
    for candidate in range(args.port,args.port+20):
        try:
            existing=json.loads(urllib.request.urlopen(f'http://127.0.0.1:{candidate}/api/health',timeout=.3).read())
            if existing.get('installationId')==INSTALLATION_ID:
                if not args.no_browser:open_window(f'http://127.0.0.1:{candidate}')
                return
        except Exception:pass
        with socket.socket() as probe:
            try:probe.bind(('127.0.0.1',candidate))
            except OSError:continue
        args.port=candidate;break
    else:raise RuntimeError('No free local app port. Close unused app instances and try again.')
    engine.resource_plan.cleanup_abandoned(DATA)
    files=[p for constant in CONSTANTS for suffix in ('txt','ycd','mpt') for p in DATA.glob(f'{constant}-*.{suffix}')]
    preferred=None
    try:
        active=json.loads((DATA/'active-dataset.json').read_text())['file']
        if Path(active).name==active and DATA/active in files:preferred=DATA/active
    except (OSError,ValueError,KeyError):pass
    if files:
        try: load_file(preferred or max(files,key=lambda f:int(f.stem.split('-')[-1]) if f.stem.split('-')[-1].isdigit() else f.stat().st_size))
        except Exception: traceback.print_exc()
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print(f'Pi Explorer · http://127.0.0.1:{args.port}',flush=True)
    (DATA/'server.json').write_text(json.dumps({'pid':os.getpid(),'port':args.port}))
    if not args.no_browser: threading.Timer(.35,open_window,args=(f'http://127.0.0.1:{args.port}',)).start()
    try: server.serve_forever()
    finally:
        for job in JOBS.values(): job['cancel']=True
        server.server_close();POOL.shutdown(wait=False,cancel_futures=True)

if __name__=='__main__': main()
