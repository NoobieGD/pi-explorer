"""Incremental native status parsing and low-overhead local process telemetry."""
import os,re,time,threading,codecs,ctypes
from collections import deque
from ctypes import wintypes as w

# Percentages belong to the current native phase. Overall values are only
# coarse scheduling estimates retained for older clients, never digits done.
PHASES={
 'prepare':('Preparing calculator',1,.01),
 'series':('Series summation',2,.05),
 'divide':('Large division',3,.72),
 'sqrt':('Square root',4,.80),
 'multiply':('Large multiplication',5,.84),
 'multiply_verify':('Checking multiplication',5,.87),
 'hex':('Preparing conversion',6,.88),
 'convert':('Decimal conversion',6,.90),
 'write':('Writing decimal digits',7,.95),
 'base_verify':('Checking decimal conversion',8,.97),
 'output_verify':('Verifying saved digits',8,.985),
 'cleanup':('Clearing temporary files',9,.995),
 'complete':('Native output verified',9,1),
}
MARKERS=[('Series Common','series'),('Large Division...','divide'),('InvSqrt(','sqrt'),
 ('Verifying Large Multiply','multiply_verify'),('Large Multiply...','multiply'),
 ('Processing Hexadecimal Digits','hex'),('Base Converting:','convert'),
 ('Writing Decimal Digits:','write'),('Verifying Base Conversion:','base_verify'),
 ('Verifying Decimal Output:','output_verify')]
ANSI=re.compile(r'\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))')

class NativeProgress:
    def __init__(self,count):
        self.count=count;self.lock=threading.Lock();self.phase='prepare';self.percent=None
        self.started=time.monotonic();self.phase_started=self.started;self.last_native=self.started
        self.pending='';self.decoder=codecs.getincrementaldecoder('utf-8')('replace')
        self.tail=deque();self.tail_bytes=0;self.total_time=False;self.verified=False;self.native_updates=0
    def set_phase(self,phase):
        with self.lock:self._phase(phase)
    def _phase(self,phase):
        if phase!=self.phase:self.phase=phase;self.percent=None;self.phase_started=time.monotonic()
    def _line(self,line,final=False):
        line=ANSI.sub('',line).strip()
        if not line:return
        for marker,phase in MARKERS:
            if marker in line:self._phase(phase);break
        previous=self.percent
        if self.phase=='series':
            found=re.search(r'Summing:\s*(\d+(?:\.\d+)?)%',line)
            if found:self.percent=max(0,min(1,float(found[1])/100))
        if self.phase=='output_verify':
            found=re.search(r'Verifying\.\.\.\s*([\d,]+)\s+digits hashed',line)
            if found:self.percent=min(1,int(found[1].replace(',',''))/self.count)
        if self.percent!=previous:self.last_native=time.monotonic();self.native_updates+=1
        if 'Total Computation Time:' in line:self.total_time=True
        found=re.search(r'Spot Check: Good through ([\d,]+)',line)
        if final and found and int(found[1].replace(',',''))==self.count:self.verified=True
    def feed(self,data):
        with self.lock:
            tail=data[-128*1024:];self.tail.append(tail);self.tail_bytes+=len(tail)
            while self.tail_bytes>128*1024 and len(self.tail)>1:self.tail_bytes-=len(self.tail.popleft())
            self.pending+=self.decoder.decode(data)
            lines=re.split(r'[\r\n]',self.pending);self.pending=lines.pop()[-4096:]
            for line in lines:self._line(line,True)
            # An overwritten status often has no trailing newline yet.
            self._line(self.pending)
    def finish(self):
        with self.lock:
            self.pending+=self.decoder.decode(b'',final=True);self._line(self.pending,True);self.pending=''
    def snapshot(self):
        with self.lock:
            now=time.monotonic();label,step,overall=PHASES[self.phase]
            return {'phase':self.phase,'phaseLabel':label,'phaseStep':step,'phaseSteps':9,
                    'phaseProgress':self.percent,'overallEstimate':overall,
                    'phaseElapsed':now-self.phase_started,'nativeElapsed':now-self.started,
                    'nativeUpdateAge':now-self.last_native,'nativeUpdates':self.native_updates,
                    'updatedAt':time.time(),'verified':self.verified,'progressKind':'phase'}
    def transcript_tail(self):
        with self.lock:return b''.join(self.tail)[-128*1024:]

class ProcessSampler:
    """CPU, resident RAM and process I/O for the native launcher and children."""
    def __init__(self,pid):
        self.pid=pid;self.handles={};self.previous={};self.refresh_at=0;self.sample_at=time.monotonic()
        self.available=os.name=='nt'
        if not self.available:return
        self.api=ctypes.WinDLL('kernel32',use_last_error=True);self.psapi=ctypes.WinDLL('psapi',use_last_error=True)
        class Entry(ctypes.Structure):
            _fields_=[('dwSize',w.DWORD),('cntUsage',w.DWORD),('pid',w.DWORD),('heap',ctypes.c_size_t),('module',w.DWORD),('threads',w.DWORD),('parent',w.DWORD),('priority',w.LONG),('flags',w.DWORD),('exe',w.WCHAR*260)]
        class Memory(ctypes.Structure):
            _fields_=[('cb',w.DWORD),('faults',w.DWORD)]+[(key,ctypes.c_size_t) for key in ('peak','working','peakPaged','paged','peakNonPaged','nonPaged','pagefile','peakPagefile','private')]
        class IO(ctypes.Structure):
            _fields_=[(key,ctypes.c_ulonglong) for key in ('readOps','writeOps','otherOps','read','write','other')]
        self.Entry=Entry;self.Memory=Memory;self.IO=IO
        a=self.api
        a.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];a.CreateToolhelp32Snapshot.restype=w.HANDLE
        a.Process32FirstW.argtypes=[w.HANDLE,ctypes.POINTER(Entry)];a.Process32NextW.argtypes=[w.HANDLE,ctypes.POINTER(Entry)]
        a.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];a.OpenProcess.restype=w.HANDLE
        a.CloseHandle.argtypes=[w.HANDLE]
        a.GetProcessTimes.argtypes=[w.HANDLE,*([ctypes.POINTER(w.FILETIME)]*4)]
        a.GetProcessIoCounters.argtypes=[w.HANDLE,ctypes.POINTER(IO)]
        self.psapi.GetProcessMemoryInfo.argtypes=[w.HANDLE,ctypes.POINTER(Memory),w.DWORD]
    def _refresh(self,now):
        if now<self.refresh_at:return
        self.refresh_at=now+(.25 if len(self.handles)<2 else 5);parents={};a=self.api;handle=a.CreateToolhelp32Snapshot(2,0)
        if handle in (None,ctypes.c_void_p(-1).value):return
        try:
            entry=self.Entry();entry.dwSize=ctypes.sizeof(entry);valid=a.Process32FirstW(handle,ctypes.byref(entry))
            while valid:parents[entry.pid]=entry.parent;valid=a.Process32NextW(handle,ctypes.byref(entry))
        finally:a.CloseHandle(handle)
        wanted={self.pid}
        while True:
            extra={pid for pid,parent in parents.items() if parent in wanted}-wanted
            if not extra:break
            wanted|=extra
        for pid in wanted-self.handles.keys():
            value=a.OpenProcess(0x1000,False,pid)
            if value:self.handles[pid]=value
        for pid in list(self.handles):
            if pid not in wanted or pid not in parents:a.CloseHandle(self.handles.pop(pid));self.previous.pop(pid,None)
    def sample(self):
        if not self.available:return {}
        now=time.monotonic();self._refresh(now);elapsed=max(.001,now-self.sample_at);self.sample_at=now
        cpu=read=write=ram=0
        for pid,handle in self.handles.items():
            creation,exit_time,kernel,user=(w.FILETIME() for _ in range(4));io=self.IO();memory=self.Memory();memory.cb=ctypes.sizeof(memory)
            if not self.api.GetProcessTimes(handle,ctypes.byref(creation),ctypes.byref(exit_time),ctypes.byref(kernel),ctypes.byref(user)):continue
            ticks=((kernel.dwHighDateTime<<32)|kernel.dwLowDateTime)+((user.dwHighDateTime<<32)|user.dwLowDateTime)
            self.api.GetProcessIoCounters(handle,ctypes.byref(io))
            if self.psapi.GetProcessMemoryInfo(handle,ctypes.byref(memory),ctypes.sizeof(memory)):ram+=memory.working
            old=self.previous.get(pid)
            if old:cpu+=max(0,ticks-old[0]);read+=max(0,io.read-old[1]);write+=max(0,io.write-old[2])
            self.previous[pid]=(ticks,io.read,io.write)
        return {'cpuPercent':min(100,cpu/1e7/elapsed/(os.cpu_count() or 1)*100),'residentBytes':ram,
                'readBytesPerSecond':read/elapsed,'writeBytesPerSecond':write/elapsed,'processCount':len(self.handles)}
    def close(self):
        for handle in self.handles.values():self.api.CloseHandle(handle)
        self.handles.clear()
