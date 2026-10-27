"""Zero-copy native searches, bounded parallelism and a small exact-result LRU.

The DLL releases the GIL via ctypes.CDLL. Only mapped input pages and at most
workers*(limit+1) 64-bit match offsets are used, irrespective of dataset size.
"""
import ctypes as c
import os,time,threading
from pathlib import Path
from collections import OrderedDict
from concurrent.futures import ThreadPoolExecutor

ROOT=Path(__file__).resolve().parent
WORKERS=min(8,os.cpu_count() or 1)
def _performance_worker():
    # Hidden pythonw processes can receive a low inferred Windows QoS. Search
    # contributes directly to the visible GUI, so tag only these workers HighQoS.
    if os.name!='nt':return
    try:
        kernel=c.WinDLL('kernel32',use_last_error=True)
        class PowerState(c.Structure):_fields_=[('version',c.c_ulong),('control',c.c_ulong),('state',c.c_ulong)]
        setter=kernel.SetThreadInformation
        setter.argtypes=[c.c_void_p,c.c_int,c.c_void_p,c.c_ulong];setter.restype=c.c_int
        value=PowerState(1,1,0);setter(c.c_void_p(-2),3,c.byref(value),c.sizeof(value))
    except (OSError,AttributeError):pass
POOL=ThreadPoolExecutor(max_workers=WORKERS,thread_name_prefix='pi-scan',initializer=_performance_worker)
_CACHE=OrderedDict();_LOCK=threading.Lock();CACHE_LIMIT=64
_DLL=None;LOAD_ERROR=None
_PREFETCH=None
class MemoryRange(c.Structure):_fields_=[('address',c.c_void_p),('length',c.c_size_t)]
if os.name=='nt':
    try:
        _PREFETCH=c.WinDLL('kernel32',use_last_error=True).PrefetchVirtualMemory
        _PREFETCH.argtypes=[c.c_void_p,c.c_size_t,c.POINTER(MemoryRange),c.c_ulong];_PREFETCH.restype=c.c_int
    except (OSError,AttributeError):pass
try:
    _DLL=c.CDLL(str(ROOT/'native/pi_scan.dll'))
    _DLL.pi_scan_avx2.restype=c.c_int
    _DLL.pi_scan.argtypes=[c.c_void_p,c.c_uint64,c.c_char_p,c.c_uint64,c.c_int,c.c_uint64,c.c_uint64,c.POINTER(c.c_uint64),c.c_uint64,c.c_int]
    _DLL.pi_scan.restype=c.c_uint64
    _DLL.pi_shape.argtypes=[c.c_void_p,c.c_uint64,c.c_uint64,c.c_uint64,c.POINTER(c.c_uint64),c.c_char_p,c.c_uint64,c.c_uint64,c.c_uint64,c.c_uint64,c.c_int,c.POINTER(c.c_uint64),c.c_uint64]
    _DLL.pi_shape.restype=c.c_uint64
except OSError as exc:LOAD_ERROR=str(exc)

class Buffer(c.Structure):
    _fields_=[('buf',c.c_void_p),('obj',c.c_void_p),('len',c.c_ssize_t),('itemsize',c.c_ssize_t),
              ('readonly',c.c_int),('ndim',c.c_int),('format',c.c_void_p),('shape',c.c_void_p),
              ('strides',c.c_void_p),('suboffsets',c.c_void_p),('internal',c.c_void_p)]
_GET=c.pythonapi.PyObject_GetBuffer;_GET.argtypes=[c.py_object,c.POINTER(Buffer),c.c_int];_GET.restype=c.c_int
_RELEASE=c.pythonapi.PyBuffer_Release;_RELEASE.argtypes=[c.POINTER(Buffer)];_RELEASE.restype=None

def available():return _DLL is not None
def features():return {'backend':'AVX2' if _DLL and _DLL.pi_scan_avx2() else 'scalar' if _DLL else 'Python','workers':WORKERS,'boundedPrefetch':bool(_PREFETCH),'loadError':LOAD_ERROR}
def clear_cache():
    with _LOCK:_CACHE.clear()

def _get(key):
    with _LOCK:
        if key not in _CACHE:return None
        value=_CACHE.pop(key);_CACHE[key]=value
        return value

def _put(key,value):
    with _LOCK:
        _CACHE[key]=value;_CACHE.move_to_end(key)
        while len(_CACHE)>CACHE_LIMIT:_CACHE.popitem(last=False)

def _identity(store):
    # Include the full path and file identity, not just the display name.
    stat=os.fstat(store.file.fileno())
    return str(store.path.resolve()),stat.st_mtime_ns,stat.st_size,stat.st_ino

def sequence(store,query,mode='digits',scheme='mod26',alignment=0,limit=300,
             cancelled=lambda:False,progress=None,metrics=None,threads=None,use_cache=True,vector=True,prefetch=None):
    if not _DLL:return None
    if cancelled():raise InterruptedError('Search cancelled')
    if not query:raise ValueError('Enter a nonempty pattern')
    if limit<1:raise ValueError('Result limit must be positive')
    if mode=='text' and scheme not in ('mod26','a1z26','ascii'):raise ValueError('Unknown text encoding')
    kind=(3 if scheme=='ascii' else 2 if scheme=='a1z26' else 1) if mode=='text' else 0
    step=3 if kind==3 else 2 if kind else 1
    if kind and not 0<=alignment<step:raise ValueError('Invalid text alignment')
    total=store.total_units(mode,scheme,alignment)
    count=max(0,total-len(query)+1)
    key=(_identity(store),'sequence',bytes(query),mode,scheme,alignment,limit)
    cached=_get(key) if use_cache else None
    if cached is not None:
        positions,capped,scanned=cached
        if metrics is not None:metrics.update(backend='Exact result cache',cacheHit=True,scanned=scanned,threads=0,sourceDigits=scanned*step)
        if progress:progress(1,'Loaded the exact result for this dataset and encoding')
        return list(positions),capped,0
    valid=all(65<=v<=90 for v in query) if kind==1 else all(v==46 or 65<=v<=90 for v in query) if kind==2 else all(32<=v<=126 for v in query) if kind==3 else True
    if not valid or not count:
        if metrics is not None:metrics.update(backend='Encoding validation',cacheHit=False,scanned=0,sourceDigits=0,threads=0)
        return [],False,0
    workers=max(1,min(WORKERS,int(threads or (min(4,WORKERS) if kind!=3 else WORKERS))))
    # Smaller resident files measured faster without an extra OS hint. Larger
    # streaming files benefit from bounded concurrent disk read requests.
    if prefetch is None:prefetch=len(store)>2*1024**3
    # 16 MiB of source digits per task: bounded cancellation and sequential I/O.
    chunk=max(256*1024,16*1024*1024//step)
    if count<4*1024*1024:workers=1
    lease=Buffer();_GET(store.mapping,c.byref(lease),0)
    pointer=lease.buf+store.offset+(alignment if kind else 0)
    matches=[];scanned=0;last_report=0;pending=[]
    def scan(begin,end):
        # A bounded strong hint lets Windows batch disk I/O instead of faulting
        # in one page at a time. Failure under memory pressure is harmless.
        if prefetch and _PREFETCH and len(query)>=(6 if kind else 8):
            region=MemoryRange(pointer+begin*step,(end-begin+len(query)-1)*step)
            _PREFETCH(c.c_void_p(-1),1,c.byref(region),0)
        out=(c.c_uint64*(limit+1))()
        n=_DLL.pi_scan(pointer,total,query,len(query),kind,begin,end,out,limit+1,int(vector))
        return list(out[:n])
    try:
        for wave in range(0,count,chunk*workers):
            if cancelled():raise InterruptedError('Search cancelled')
            ranges=[(begin,min(count,begin+chunk)) for begin in range(wave,min(count,wave+chunk*workers),chunk)]
            pending=[POOL.submit(scan,begin,end) for begin,end in ranges]
            # Merge in source order, preserving overlapping matches and first-N semantics.
            for (begin,end),future in zip(ranges,pending):
                positions=future.result();scanned=end
                if cancelled():raise InterruptedError('Search cancelled')
                matches.extend(positions[:max(0,limit+1-len(matches))])
                if len(matches)>limit:
                    scanned=matches[limit]+1;break
                now=time.perf_counter()
                if progress and now-last_report>=.08:
                    progress(end/max(count,1),f'Scanned {end:,} of {total:,} characters · {workers} native threads');last_report=now
            # Keep the mmap buffer leased until all native reads have finished.
            for future in pending:future.result()
            pending=[]
            if len(matches)>limit:break
    finally:
        try:
            for future in pending:future.cancel()
            for future in pending:
                if not future.cancelled():future.result()
        finally:_RELEASE(c.byref(lease))
    capped=len(matches)>limit;matches=matches[:limit]
    # Candidate ranges include their query halo. A capped scan never claims the full file.
    scanned=min(total,scanned+len(query)-1)
    if metrics is not None:metrics.update(backend=('AVX2' if _DLL.pi_scan_avx2() and vector else 'Native scalar')+' parallel scan',cacheHit=False,scanned=scanned,sourceDigits=scanned*step,threads=workers)
    if use_cache:_put(key,(tuple(matches),capped,scanned))
    return matches,capped,0

def shapes(store,rows,widths,rule='threshold',limit=60,cancelled=lambda:False,progress=None,metrics=None,use_cache=True):
    if not _DLL:return None
    rows=list(rows);widths=sorted(set(int(width) for width in widths))
    if not rows or not widths:raise ValueError('Choose a pixel pattern and valid row widths')
    w=len(rows[0]);h=len(rows)
    widths=[width for width in widths if w<=width<=4096]
    if not 1<=h<=24 or not widths or limit<1:raise ValueError('Invalid shape dimensions or row widths')
    if not 1<=w<=24 or any(len(row)!=w or any(ch not in '01?' for ch in row) for row in rows):raise ValueError('Invalid pixel pattern')
    cells=[(y,x,int(ch)) for y,row in enumerate(rows) for x,ch in enumerate(row) if ch!='?']
    if not cells:raise ValueError('Choose at least one constrained pixel')
    key=(_identity(store),'shape',tuple(rows),tuple(widths),rule,limit)
    cached=_get(key) if use_cache else None
    if cached is not None:
        found,capped,scanned=cached
        if metrics is not None:metrics.update(backend='Exact result cache',cacheHit=True,scanned=scanned,sourceDigits=scanned,threads=0)
        return [dict(m) for m in found],capped
    # Spread the first filters over the shape, to reject candidates early.
    ordered=cells[::2]+cells[1::2]
    lease=Buffer();_GET(store.mapping,c.byref(lease),0);pointer=lease.buf+store.offset
    chunk=2*1024*1024;matches=[];scanned=0;pending=[];last_report=0
    def scan(start,end,width):
        extent=(h-1)*width+w
        offsets=(c.c_uint64*len(ordered))(*(y*width+x for y,x,ch in ordered))
        values=bytes(ch for y,x,ch in ordered);out=(c.c_uint64*(limit+1))()
        n=_DLL.pi_shape(pointer,len(store),start,end,offsets,values,len(ordered),extent,width,w,rule=='parity',out,limit+1)
        return [{'index':int(p),'position':int(p)+1,'width':width,'height':h,'shapeWidth':w} for p in out[:n]]
    try:
        spatial=max(1,WORKERS//len(widths))
        for wave in range(0,len(store),chunk*spatial):
            if cancelled():raise InterruptedError('Search cancelled')
            tasks=[(start,min(len(store),start+chunk),width) for start in range(wave,min(len(store),wave+chunk*spatial),chunk) for width in widths]
            block=[]
            # Parallelize spatially for one width and across widths for a sweep.
            for wi in range(0,len(tasks),WORKERS):
                pending=[POOL.submit(scan,*task) for task in tasks[wi:wi+WORKERS]]
                for future in pending:block.extend(future.result())
                pending=[]
                if cancelled():raise InterruptedError('Search cancelled')
            block.sort(key=lambda m:(m['index'],m['width']));matches.extend(block[:limit+1-len(matches)])
            scanned=min(len(store),wave+chunk*spatial);end=scanned
            if len(matches)>limit:break
            now=time.perf_counter()
            if progress and now-last_report>.08:progress(end/len(store),f'Searched {end:,} of {len(store):,} digits · {len(widths)} widths · native SIMD');last_report=now
    finally:
        try:
            for future in pending:future.cancel()
            for future in pending:
                if not future.cancelled():future.result()
        finally:_RELEASE(c.byref(lease))
    capped=len(matches)>limit;matches=matches[:limit]
    if metrics is not None:metrics.update(backend='Native SIMD pixel scan',cacheHit=False,scanned=scanned,sourceDigits=scanned,threads=WORKERS,widths=len(widths))
    if use_cache:_put(key,(tuple(dict(m) for m in matches),capped,scanned))
    return matches,capped
