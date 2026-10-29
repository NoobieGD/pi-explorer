"""Exact pi digits and deterministic encodings. All positions are 1-based, after 3."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent / 'vendor'))
import gmpy2 as g
import math
import time
import hashlib
import json
import subprocess
import os
import re
import platform
from storage import atomic_write, write_progress
from digit_store import transform, DigitStore, equal_files
import numpy as np
import resource_plan
from constants import identify,CONSTANTS,compute as compute_constant

MAX_DIGITS = None  # No application digit ceiling; preflight checks actual resources.
ROOT=Path(__file__).resolve().parent
from native_install import find_native,require_native
YCRUNCHER=find_native()
PALETTE = ['#ef5350','#ff9e40','#f6d85d','#78cb70','#39bba0',
           '#42b9d5','#5486e8','#a67ce8','#e578b3','#e4e7ee']

def compute_pi(count, method='chudnovsky', progress=None):
    """Chudnovsky binary splitting, integer square root and 32 guard digits.

    No float arithmetic enters the decimal result. MPFR is an independent
    correctly-rounded native implementation available for comparison.
    """
    count = resource_plan.digit_count(count)
    if method=='compact':return compute_compact(count,progress)[0]
    if count>20_000_000:computation_plan(count,ROOT/'data',method,'ram')
    if progress:
        progress(.02, 'Preparing native arithmetic')
    n = count + 32
    if method == 'mpfr':
        with g.context(precision=math.ceil((n + 4) * math.log2(10)), round=g.RoundToZero):
            pi = g.const_pi()
            if progress: progress(.72, 'Converting binary precision to decimal')
            mantissa, exponent, _ = pi.digits(10, n + 1)
            assert exponent == 1
            return mantissa[1:count+1]
    if method != 'chudnovsky':
        raise ValueError('Unknown arithmetic engine')
    terms = n // 14 + 1
    c = g.mpz(640320) ** 3 // 24
    completed = 0
    next_update = max(1, terms // 32)
    def split(a, b):
        nonlocal completed, next_update
        if b-a == 1:
            if a == 0:
                p = q = g.mpz(1)
            else:
                p = g.mpz(6*a-5)*(2*a-1)*(6*a-1)
                q = g.mpz(a)**3*c
            t = p*(13591409+545140134*a)
            if a & 1: t = -t
            completed += 1
            if progress and completed >= next_update:
                progress(.05 + .56 * completed/terms, 'Chudnovsky · binary splitting')
                next_update += max(1, terms//32)
            return p,q,t
        m = (a+b)//2
        p1,q1,t1 = split(a,m)
        p2,q2,t2 = split(m,b)
        return p1*p2,q1*q2,t1*q2+p1*t2
    _,q,t = split(0,terms)
    if progress: progress(.68, 'Computing integer square root')
    root = g.isqrt(g.mpz(10005)*g.mpz(10)**(2*n))
    if progress: progress(.83, 'Final division and decimal conversion')
    result = str((q*426880*root)//t)
    if len(result) != n+1 or not result.startswith('3141592653589793238'[:min(n+1,19)]):
        raise ArithmeticError('Pi verification failed')
    if progress: progress(.97, 'Verifying prefix and saving digits')
    return result[1:count+1]

def compute_compact(count,progress=None):
    from research.compact_engine import compute
    admission=computation_plan(count,ROOT/'data','compact','ram')
    if not admission['launchable']:raise MemoryError(admission['message'])
    digits,stats=compute(count,progress=progress)
    if progress:progress(.94,'Compact · independent MPFR verification')
    expected=compute_pi(count,'mpfr')
    if digits!=expected:raise ArithmeticError('Compact output disagrees with independent MPFR')
    if progress:progress(.98,'Compact · all digits verified')
    stats['verification']='Full independent MPFR comparison'
    return digits,stats

def letters(digits, scheme='mod26', alignment=0):
    return transform(digits,'text',scheme,alignment=alignment)

def binary(digits, rule='threshold'):
    table = bytes((49 if (v >= 5 if rule == 'threshold' else v % 2) else 48)
                  if 48 <= i <= 57 else i for i in range(256) for v in [i-48])
    if rule not in ('threshold','parity'): raise ValueError('Unknown pixel mapping')
    return digits.translate(table)

def find_matches(data, query, limit=300, cancelled=None):
    matches=[]
    pos=0
    while len(matches)<limit:
        if cancelled and cancelled(): raise InterruptedError('Search cancelled')
        p=data.find(query,pos)
        if p<0: return matches,False
        matches.append(p)
        pos=p+1  # overlapping occurrences count
    return matches,data.find(query,pos)>=0

def find_shapes(bits, rows, widths, limit=60, progress=None, cancelled=None, base_index=0,start_limit=None,source_bits=None):
    """Native row-mask intersections, without a giant 2D allocation.

    Rows use '0', '1', '?' (wildcard). A candidate cannot wrap a row boundary.
    Each bit represents a candidate start; row masks are shared across widths.
    """
    if not rows or not 1 <= len(rows) <= 24: raise ValueError('Shape must be 1–24 rows')
    w=len(rows[0]); h=len(rows)
    if not 1 <= w <= 24 or any(len(r)!=w for r in rows): raise ValueError('Invalid shape dimensions')
    if any(ch not in '01?' for row in rows for ch in row): raise ValueError('Invalid pixel')
    if not any(ch!='?' for row in rows for ch in row): raise ValueError('Draw at least one constrained pixel')
    results=[]
    widths=sorted(set(int(v) for v in widths if w <= int(v) <= 4096))
    if not widths: raise ValueError('Row width must fit the shape')
    # Each bit is a candidate start. GMP intersects millions of candidates
    # with native word operations; a shift tests every candidate at once.
    source=source_bits if source_bits is not None else g.mpz(bits[::-1],2) if bits else g.mpz(0)
    # Cache each complete row as a candidate mask. Repeated shape rows share
    # their work; a width then needs h intersections rather than w*h.
    row_masks={}
    row_limit=(g.mpz(1)<<max(0,len(bits)-w+1))-1
    for row in set(rows):
        mask=row_limit
        for x,ch in enumerate(row):
            if ch=='?': continue
            shifted=source>>x
            mask &= shifted if ch=='1' else ~shifted
        row_masks[row]=mask
    for wi,stride in enumerate(widths):
        if progress: progress(wi/len(widths), f'Searching row width {stride}')
        size=len(bits)-(h-1)*stride-w+1
        if start_limit is not None:size=min(size,start_limit)
        if size<=0: continue
        candidates=(g.mpz(1)<<size)-1
        for y,row in enumerate(rows):
            if cancelled and cancelled(): raise InterruptedError('Search cancelled')
            candidates &= row_masks[row]>>(y*stride)
            if not candidates: break
        while candidates:
            p=int(g.bit_scan1(candidates))
            candidates=g.bit_clear(candidates,p)
            if (p+base_index)%stride+w<=stride:
                results.append({'index':p,'position':p+1,'width':stride,'height':h,'shapeWidth':w})
                if len(results)>=limit: return sorted(results,key=lambda m:(m['index'],m['width'])), True
    results.sort(key=lambda m:(m['index'],m['width']))
    return results,False

def statistics(digits):
    if hasattr(digits,'chunks'):
        counts=np.zeros(10,dtype=np.int64);digest=hashlib.sha256();longest={'digit':'','length':0,'position':0};offset=0;last=None;run=0
        for chunk in digits.chunks():
            digest.update(chunk);a=np.frombuffer(chunk,dtype=np.uint8);counts+=np.bincount(a-48,minlength=10)
            changes=np.flatnonzero(a[1:]!=a[:-1])+1
            starts=np.concatenate(([0],changes));ends=np.concatenate((changes,[len(a)]));lengths=ends-starts
            if len(a) and last==int(a[0]):lengths[0]+=run
            at=int(np.argmax(lengths));nrun=int(lengths[at]);position=offset+int(ends[at])-nrun+1
            if nrun>longest['length']:longest={'digit':str(int(a[int(starts[at])])-48),'length':nrun,'position':position}
            run=int(lengths[-1]);last=int(a[-1]);offset+=len(a)
        n=len(digits);values=counts.tolist();entropy=-sum(v/n*math.log2(v/n) for v in values if v) if n else 0
        return {'counts':values,'entropy':entropy,'chiSquare':sum((v-n/10)**2/(n/10) for v in values) if n else 0,'longestRun':longest,'sha256':digest.hexdigest(),'count':n}
    n=len(digits)
    counts=[digits.count(str(i).encode()) for i in range(10)]
    entropy=-sum((v/n)*math.log2(v/n) for v in counts if v) if n else 0
    chi=sum((v-n/10)**2/(n/10) for v in counts) if n else 0
    longest={'digit':'','length':0,'position':0}
    for i in range(10):
        if not counts[i]: continue
        token=str(i).encode(); size=2; first=-1
        while True:
            at=digits.find(token*size)
            if at<0: break
            first=at;size+=1
        if size-1>longest['length']:
            longest={'digit':str(i),'length':size-1,'position':first+1 if first>=0 else digits.find(token)+1}
    return {'counts':counts,'entropy':entropy,'chiSquare':chi,'longestRun':longest,
            'sha256':hashlib.sha256(digits).hexdigest(),'count':n}

def available_memory():
    if os.name!='nt':return 8*1024**3
    import ctypes
    class Status(ctypes.Structure):
        _fields_=[('length',ctypes.c_ulong),('load',ctypes.c_ulong)]+[(k,ctypes.c_ulonglong) for k in ('total','available','pageTotal','pageAvailable','virtualTotal','virtualAvailable','extra')]
    value=Status();value.length=ctypes.sizeof(value);ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(value));return value.available

def native_memory_estimate(count):return resource_plan.estimate_ram(count)

def auto_native(count,mode='auto',memory_mib=0):
    return YCRUNCHER.exists() and (mode=='disk' or count>=2_000_000 or count*14+40*resource_plan.MIB>resource_plan.ram_budget(available_memory(),memory_mib))

def computation_plan(count,folder=ROOT/'data',method='auto',mode='auto',memory_mib=0,constant='pi'):
    count=resource_plan.digit_count(count)
    constant=identify(constant)
    if constant!='pi' and method in ('tachuspi','compact'):raise ValueError('TachusPI and Compact are pi-only; choose Auto, Exact GMP or MPFR')
    if method=='auto' and not auto_native(count,mode,memory_mib):method='exact'
    if constant!='pi':
        low_disk=method in ('auto','ycruncher-low')
        return resource_plan.plan(count,folder,available_memory(),'ycruncher' if low_disk else method,mode,memory_mib,low_disk=low_disk,constant=constant)
    if method=='tachuspi':
        import tachuspi
        return tachuspi.plan(count,folder,available_memory(),mode,memory_mib)
    if method=='compact':
        from research.compact_engine import plan as compact_plan
        count=resource_plan.digit_count(count);available=available_memory();report=compact_plan(count)
        try:
            result=resource_plan.plan(count,folder,available,method,mode,memory_mib)
            result.update(launchable=True,message='Experimental compact engine · RAM only · full MPFR verification')
        except (MemoryError,OSError,ValueError) as error:
            detail='This RAM-only engine exceeds the safe budget. Use Auto for disk-backed calculations.' if isinstance(error,MemoryError) else str(error)
            result={'digits':count,'mode':'ram','launchable':False,'availableBytes':available,
                    'ramBudgetBytes':resource_plan.ram_budget(available,memory_mib),'estimatedBytes':count*14+40*resource_plan.MIB,
                    'outputBytes':count+2,'peakDiskBytes':None,'requiresElevation':False,
                    'message':'Compact engine cannot run this request: '+detail}
        max_digits=max(0,(resource_plan.ram_budget(available,memory_mib)-40*resource_plan.MIB)//14)
        return {**result,'method':'compact','experimental':True,'storageVerification':report,'compactMaxDigitsForRam':max_digits}
    low_disk=method=='ycruncher-low'
    if method=='auto' and YCRUNCHER.exists() and mode!='ram':
        try:return resource_plan.plan(count,folder,available_memory(),method,mode,memory_mib)
        except OSError:
            result=resource_plan.plan(count,folder,available_memory(),'ycruncher',mode,memory_mib,low_disk=True)
            result['preferredMethod']='ycruncher-low';return result
    return resource_plan.plan(count,folder,available_memory(),'ycruncher' if low_disk else method,mode,memory_mib,low_disk=low_disk)

def check_native_memory(count):
    required=native_memory_estimate(count);available=available_memory()
    if count>=100_000_000 and required+256*1024**2>available:
        raise MemoryError(f'{count:,} digits need approximately {required/1024**3:.1f} GiB of free RAM; {available/1024**3:.1f} GiB is available. Close memory-heavy apps or choose fewer digits. The app will not force Windows into excessive paging.')
    return {'estimatedBytes':required,'availableBytes':available}

def stop_native(proc):
    from native_runner import stop_native as stop
    return stop(proc)

def compute_ycruncher_file(count,folder,progress=None,options=None,deadline=None,cancelled=None,on_native_job=None):
    """Run the official CPU-dispatching, multithreaded y-cruncher backend."""
    require_native(YCRUNCHER)
    folder=Path(folder).resolve()
    import secrets
    options={'priority':0,**(options or {})}
    constant=identify(options.get('constant','pi'))
    plan=computation_plan(count,folder,'ycruncher-low' if options.get('lowDisk') else 'ycruncher',options.get('storageMode','auto'),options.get('memoryMiB',0),constant=constant)
    work=folder/'native-output'/f'run-{count}-{secrets.token_hex(4)}';work.mkdir(parents=True)
    logfile=work/'console.log'
    request={'digits':count,'ownerPid':os.getpid(),'plan':plan,'options':options,'deadline':deadline}
    atomic_write(work/'job.json',json.dumps({'owner':'Pi Explorer scratch v1','ownerPid':os.getpid()}))
    atomic_write(work/'request.json',json.dumps(request))
    import native_runner
    started=time.perf_counter()
    if progress: progress(.02,'Windows approval needed for disk-backed blocks' if plan['mode']=='disk' and os.name=='nt' else 'y-cruncher · selecting CPU instruction set')
    if on_native_job:on_native_job(work,plan)
    admin=os.name=='nt' and bool(__import__('ctypes').windll.shell32.IsUserAnAdmin())
    proc=None;cancel_sent=False
    try:
        proc=native_runner.launch(work/'request.json',elevate=plan['mode']=='disk' and os.name=='nt' and not admin)
        while proc.poll() is None:
            if (cancelled and cancelled()) or (deadline and time.perf_counter()-started>deadline):
                (work/'cancel').touch();cancel_sent=True
            time.sleep(.15)
        result=json.loads((work/'runner-result.json').read_text()) if (work/'runner-result.json').exists() else {}
        if result.get('status')!='completed':
            if result.get('status')=='cancelled' or (cancel_sent and cancelled and cancelled()):raise InterruptedError('Calculation cancelled')
            raise RuntimeError(result.get('error','The calculator helper could not finish.'))
    except BaseException:
        (work/'cancel').touch()
        if proc:
            for _ in range(100):
                if proc.poll() is not None:break
                time.sleep(.1)
        # The helper also watches its owner's lifetime, including forced exits.
        if not proc or proc.poll() is not None:resource_plan.cleanup(work,folder/'native-output',remove_output=True)
        raise
    finally:
        if isinstance(proc,native_runner.ElevatedProcess):proc.close()
    log=logfile.read_text(errors='replace') if logfile.exists() else ''
    candidates=list(work.glob('*Dec*.ycd' if options.get('lowDisk') else '*Dec*.txt'))
    if not candidates or not native_runner.native_verified(log,constant,0):
        resource_plan.cleanup(work,folder/'native-output',remove_output=True)
        raise RuntimeError('y-cruncher failed: '+log[-400:])
    output=max(candidates,key=lambda p:p.stat().st_mtime)
    store=DigitStore(output,constant=constant)
    valid=len(store)==count;store.close()
    if not valid:
        resource_plan.cleanup(work,folder/'native-output',remove_output=True)
        raise ArithmeticError('Native output length does not match the requested precision')
    timing=re.search(r'Total Computation Time:\s+([\d.]+)',log)
    wall=re.search(r'Start-to-End Wall Time:\s+([\d.]+)',log)
    return output,{'nativeSeconds':float(timing.group(1)) if timing else None,'nativeWallSeconds':float(wall.group(1)) if wall else None,'log':str(logfile),'options':options,'resourcePlan':plan,'supervisorCpuSeconds':result.get('supervisorCpuSeconds'),'telemetryFrames':result.get('telemetryFrames'),'nativeProgressUpdates':result.get('nativeProgressUpdates')}

def compute_ycruncher(count,folder,progress=None):
    path,info=compute_ycruncher_file(count,folder,progress)
    store=DigitStore(path)
    try:return store[:len(store)].decode('ascii'),info['nativeSeconds']
    finally:store.close()

def worker(count, method, folder, progress_name='compute-progress.json',request_name=None):
    folder=Path(folder)
    progress_file=folder/Path(progress_name).name
    started=time.perf_counter()
    def progress(value,message):
        if progress_file.with_suffix('.cancel').exists():raise InterruptedError('Calculation cancelled')
        write_progress(progress_file,value,message)
    requested=method
    packed=method=='ycruncher-low'
    request_file=folder/Path(request_name).name if request_name else None
    settings=json.loads(request_file.read_text()) if request_file and request_file.exists() else {}
    constant=identify(settings.get('constant','pi'));settings['constant']=constant
    if constant!='pi' and method in ('tachuspi','compact'):raise ValueError('This engine is pi-only')
    if requested=='auto' and auto_native(count,settings.get('storageMode','auto'),settings.get('memoryMiB',0)):
        packed=bool(computation_plan(count,folder,'auto',settings.get('storageMode','auto'),settings.get('memoryMiB',0),constant=constant).get('lowDisk'))
    if packed:settings['lowDisk']=True;method='ycruncher'
    cancel_file=progress_file.with_suffix('.cancel')
    def should_cancel():
        if cancel_file.exists():return True
        if settings.get('serverPid'):
            from native_runner import owner_alive
            return not owner_alive(int(settings['serverPid']))
        return False
    def native_job(work,plan):
        write_progress(progress_file,.02,'Windows approval needed for disk-backed blocks' if plan.get('requiresElevation') else 'Starting native calculator',nativeJob=work.name,resourcePlan=plan,progressKind='phase')
    if method=='auto': method='ycruncher' if auto_native(count,settings.get('storageMode','auto'),settings.get('memoryMiB',0)) else 'chudnovsky' if constant=='pi' else 'exact'
    if method=='chudnovsky' and constant!='pi':method='exact'
    if method=='compact' and settings.get('storageMode')=='disk':raise ValueError('The compact engine is currently RAM-only')
    if settings.get('storageMode')=='disk' and method!='tachuspi':method='ycruncher'
    native_seconds=None
    fallback=None
    path=resource_plan.dataset_path(folder,count,'mpt' if method=='tachuspi' else packed,constant=constant)
    info={}
    if method in ('ycruncher','tachuspi'):
        try:
            if method=='tachuspi':
                import tachuspi
                def tpi_telemetry(snapshot):
                    write_progress(progress_file,snapshot['overallEstimate'],'TachusPI · '+snapshot['phaseLabel'],**snapshot)
                output,info=tachuspi.compute_file(count,folder,progress,settings,cancelled=should_cancel,on_native_job=native_job,on_telemetry=tpi_telemetry)
                native_plan=info['resourcePlan']
            else:
                options_file=folder/'performance-profile.json'
                options=json.loads(options_file.read_text()) if options_file.exists() and constant=='pi' else {'ioProfile':'ssd'}
                if 'ram' in options or 'disk' in options:
                    selected=computation_plan(count,folder,'ycruncher-low' if packed else 'ycruncher',settings.get('storageMode','auto'),settings.get('memoryMiB',0))['mode']
                    identity={'processor':platform.processor(),'logicalCores':os.cpu_count()}
                    if (options.get('tunedThroughDigits') is not None and count>int(options['tunedThroughDigits'])) or (options.get('cpuSignature') and options['cpuSignature']!=identity):options={'ioProfile':'ssd'} if selected=='disk' else {}
                    else:options=dict(options.get(selected,{}))
                options.update(settings)
                native_plan=computation_plan(count,folder,'ycruncher-low' if packed else 'ycruncher',options.get('storageMode','auto'),options.get('memoryMiB',0),constant=constant)
                output,info=compute_ycruncher_file(count,folder,progress,options,cancelled=should_cancel,on_native_job=native_job)
            write_progress(progress_file,.995,'Committing verified cache',nativeJob=None,phaseProgress=None,progressKind='phase')
            if cancel_file.exists():
                resource_plan.cleanup(output.parent,folder.resolve()/'native-output',remove_output=True)
                raise InterruptedError('Calculation cancelled')
            existing=path.exists()
            if existing and not equal_files(path,output):raise ArithmeticError('Independent engines disagree with the cached digits')
            # The verified native output is the cache. A same-volume rename
            # avoids multiple billion-character strings and duplicate writes.
            if existing:output.unlink()
            else:
                for attempt in range(24):
                    try:os.replace(output,path);break
                    except PermissionError:
                        if attempt==23:raise
                        time.sleep(.05)
            saved=DigitStore(path,constant=constant);file_format='tachuspi-mpt' if method=='tachuspi' else 'ycd-packed' if getattr(saved,'packed',False) else 'integer-prefix' if saved.offset else 'raw-decimal';saved.close()
            info.update(count=count,constant=constant,integerPart=CONSTANTS[constant]['integer'],method='ycruncher-low' if packed else method,seconds=time.perf_counter()-started,sha256=None,format=file_format,verifiedOutput=True,cacheManaged=True)
            atomic_write(path.with_suffix('.json'),json.dumps(info))
            resource_plan.prune_cache(folder,keep=(path.name,settings.get('protectedCache',''),'pi-5000000.txt'))
            write_progress(progress_file,1,'Verified digits ready · scratch cleared',datasetFile=path.name,constant=constant);return
        except InterruptedError:raise
        except Exception as error:
            if method=='tachuspi' and locals().get('output'):
                resource_plan.cleanup(output.parent,folder.resolve()/'native-output',remove_output=True)
            if isinstance(error,(PermissionError,MemoryError)) or settings.get('storageMode')=='disk' or locals().get('native_plan',{}).get('mode')=='disk':raise
            if requested!='auto': raise
            computation_plan(count,folder,'chudnovsky' if constant=='pi' else 'exact','ram',constant=constant)
            fallback=str(error)
            progress(.03,'Native accelerator unavailable · using GMP')
            method='chudnovsky' if constant=='pi' else 'exact'
            digits=compute_constant(count,constant,method,progress)
    else:
        if method=='compact':digits,info['compact']=compute_compact(count,progress)
        else:digits=compute_constant(count,constant,method,progress)
    if path.exists():
        previous=DigitStore(path,constant=constant)
        try:
            if len(previous)!=len(digits) or any(previous[i:i+4*1024*1024]!=digits[i:i+4*1024*1024].encode('ascii') for i in range(0,len(digits),4*1024*1024)):raise ArithmeticError('Independent engines disagree with the cached digits')
        finally:previous.close()
    else:atomic_write(path,digits,encoding='ascii')
    info.update(count=count,constant=constant,integerPart=CONSTANTS[constant]['integer'],method=method,seconds=time.perf_counter()-started,
          nativeSeconds=native_seconds,fallback=fallback,sha256=hashlib.sha256(digits.encode()).hexdigest(),cacheManaged=True)
    atomic_write(path.with_suffix('.json'),json.dumps(info))
    resource_plan.prune_cache(folder,keep=(path.name,settings.get('protectedCache',''),'pi-5000000.txt'))
    write_progress(progress_file,1,'Ready to explore',datasetFile=path.name,constant=constant)

if __name__=='__main__':
    worker(int(sys.argv[1]),sys.argv[2],sys.argv[3],sys.argv[4] if len(sys.argv)>4 else 'compute-progress.json',sys.argv[5] if len(sys.argv)>5 else None)
