"""One native job. Only this calculator helper needs elevation for Windows disk I/O."""
import os,sys,time,json,subprocess,shutil,ctypes,re,threading
from pathlib import Path
ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT))
from storage import atomic_write
from resource_plan import checked_job,cleanup,job_bytes,MIB,digit_count
from live_progress import NativeProgress,ProcessSampler
NATIVE=ROOT/'vendor/y-cruncher/y-cruncher v0.8.7.9547b/y-cruncher.exe'
_owner_kernel=None

def stop_native(proc):
    if proc.poll() is not None:return
    if os.name=='nt':subprocess.run(['taskkill','/PID',str(proc.pid),'/T','/F'],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW)
    else:proc.terminate()

def configuration(work,count,options,plan):
    """Generate a native config from the bundled program's own saved SSD settings."""
    text=(ROOT/'vendor'/('ycruncher-reduced-template.cfg' if options.get('lowDisk') else 'ycruncher-ssd-template.cfg')).read_text(encoding='utf-8-sig')
    if options.get('lowDisk'):text=text.replace('Framework : "txt"','Framework : "ycd"\n            DigitsPerFile : 0')
    text=re.sub(r'DecimalDigits : \d+',f'DecimalDigits : {int(count)}',text)
    text=text.replace('EnableHexDigits : true','EnableHexDigits : false')
    text=re.sub(r'(?m)^(\s*)Memory : \d+',lambda m:m[1]+'Memory : '+str(int(plan['ramBudgetBytes'])),text)
    text=text.replace('Mode : "swap"','Mode : "'+('swap' if plan['mode']=='disk' else 'ram')+'"')
    # Checkpoints are never used by this wrapper: cancelled jobs clear scratch.
    # Removing these redundant copies preserves all arithmetic/output checks.
    text=text.replace('Enabled : true','Enabled : false')
    paths=iter([str(work.as_posix()),str((work/'swap').as_posix())])
    text=re.sub(r'Path : ""',lambda _: 'Path : '+json.dumps(next(paths)),text)
    tasks=max(1,min(32,int(options.get('tasks',os.cpu_count() or 1))))
    text=re.sub(r'TaskDecomposition : \d+',f'TaskDecomposition : {tasks}',text)
    cores=options.get('cores') or f'0-{(os.cpu_count() or 1)-1}'
    if not re.fullmatch(r'\d+(?:-\d+)?(?:,\d+(?:-\d+)?)*',cores):raise ValueError('Invalid native core set')
    for part in cores.split(','):
        if any(int(value)>=(os.cpu_count() or 1) for value in part.split('-')):raise ValueError('Native core set is unavailable on this CPU')
    text=re.sub(r'LogicalCores : \[[^\]]*\]','LogicalCores : ['+' '.join(json.dumps(part) for part in cores.split(','))+']',text)
    profile=options.get('tuningProfile','Kurumi')
    if profile not in ('Kurumi','SKL 6820HK (NT)'):raise ValueError('Unsupported native tuning profile')
    text=re.sub(r'TuningProfile : "[^"]*"','TuningProfile : '+json.dumps(profile),text)
    target=work/'compute.cfg';atomic_write(target,text);return target

def owner_alive(pid):
    global _owner_kernel
    if os.name!='nt':
        try:os.kill(pid,0);return True
        except OSError:return False
    from ctypes import wintypes as w
    if _owner_kernel is None:
        _owner_kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        _owner_kernel.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];_owner_kernel.OpenProcess.restype=w.HANDLE
        _owner_kernel.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];_owner_kernel.CloseHandle.argtypes=[w.HANDLE]
    api=_owner_kernel
    handle=api.OpenProcess(0x100000,False,pid)
    if not handle:return False
    try:return api.WaitForSingleObject(handle,0)==258
    finally:api.CloseHandle(handle)

def command_for(exe,work,count,options,plan):
    if (plan['mode']=='disk' and options.get('ioProfile','ssd')!='legacy') or options.get('cores') or options.get('lowDisk'):
        config=configuration(work,count,options,plan)
        return [str(exe),'skip-warnings','pause:-2','colors:0','console:linux-vterm','status:overwrite' if options.get('liveTelemetry',True) else 'status:none','priority:0','PII:-1','logfile:'+str(work/'console.log'),'config',str(config)]
    command=[str(exe),'skip-warnings','pause:-2','colors:0','console:linux-vterm','status:overwrite' if options.get('liveTelemetry',True) else 'status:none','priority:0','PII:-1',
             'logfile:'+str(work/'console.log'),'custom','pi',f'-dec:{count}','-hex:0','-od:1','-C:0','-verify:1','-mode:'+plan['mode']]
    if options.get('tuningProfile'):
        if options['tuningProfile'] not in ('Kurumi','SKL 6820HK (NT)'):raise ValueError('Unsupported native tuning profile')
        command.insert(1,'profile:'+options['tuningProfile'])
    if options.get('noSMT'):command.append('-noSMT')
    if options.get('tasks'):command.append('-TD:'+str(max(1,min(32,int(options['tasks'])))))
    if plan['mode']=='disk':
        # CLI calls this mode "swap". It is explicit blocked I/O, not OS paging.
        command[command.index('-mode:disk')]='-mode:swap'
        command+=['-M:'+str(plan['ramBudgetBytes']),'-minIO:256k','-swap:raid0',str(work/'swap')]
    return command

def run(request_path):
    work=checked_job(Path(request_path).parent,ROOT/'data/native-output')
    request=json.loads((work/'request.json').read_text());count=digit_count(request['digits']);plan=request['plan'];options=request.get('options',{})
    if plan['mode'] not in ('ram','disk'):raise ValueError('Invalid native job')
    if plan['mode']=='disk' and plan['ramBudgetBytes']<96*MIB:raise ValueError('Invalid native memory budget')
    if plan['scratchLimitBytes']<0:raise ValueError('Invalid scratch limit')
    if plan['mode']=='disk':(work/'swap').mkdir(exist_ok=True)
    proc=None;result={'status':'failed'};started=time.monotonic();cpu_started=time.process_time();last_check=0
    progress=NativeProgress(count);sampler=None;reader=None;last_publish=0;sequence=0;scratch_bytes=0;last_owner_check=0
    def publish():
        nonlocal sequence
        sequence+=1;snapshot=progress.snapshot()
        if sampler:
            try:snapshot.update(sampler.sample())
            except (OSError,ValueError):pass
        snapshot.update(sequence=sequence,scratchBytes=scratch_bytes,mode=plan['mode'])
        try:atomic_write(work/'telemetry.json',json.dumps(snapshot),retries=1)
        except OSError:pass
    publish()
    try:
        command=command_for(NATIVE,work,count,options,plan)
        proc=subprocess.Popen(command,cwd=work,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,stdin=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        sampler=ProcessSampler(proc.pid) if options.get('liveTelemetry',True) else None
        def consume():
            while data:=proc.stdout.read1(8192):progress.feed(data)
            progress.finish()
        reader=threading.Thread(target=consume,daemon=True);reader.start()
        while proc.poll() is None:
            if (work/'cancel').exists():raise InterruptedError('Calculation cancelled')
            if time.monotonic()-last_owner_check>.5:
                last_owner_check=time.monotonic()
                if not owner_alive(int(request['ownerPid'])):raise InterruptedError('Calculation cancelled')
            if request.get('deadline') and time.monotonic()-started>float(request['deadline']):raise TimeoutError('Fresh calculation exceeded the benchmark time limit')
            if progress.verified and progress.total_time:
                try:log=(work/'console.log').read_text(errors='replace')
                except OSError:log=''
                if 'Spot Check: Good through' in log and 'Total Computation Time:' in log:
                    stop_native(proc);proc.wait(timeout=10);result={'status':'completed'};break
            if time.monotonic()-last_check>1:
                last_check=time.monotonic()
                if shutil.disk_usage(work).free<plan['diskReserveBytes']:raise OSError('Stopped to preserve 2 GiB of free disk space')
                if plan['mode']=='disk':
                    scratch_bytes=job_bytes(work)
                    if scratch_bytes>plan['scratchLimitBytes']+plan['outputBytes']:raise OSError('Stopped at the temporary disk-space limit')
            if time.monotonic()-last_publish>=.25:
                last_publish=time.monotonic();publish()
            time.sleep(.05)
        if result['status']!='completed':
            log=(work/'console.log').read_text(errors='replace') if (work/'console.log').exists() else ''
            if 'Spot Check: Good through' in log and 'Total Computation Time:' in log:result={'status':'completed'}
            else:raise RuntimeError('Native computation did not verify its output. '+log[-500:])
    except Exception as error:result={'status':'cancelled' if isinstance(error,InterruptedError) else 'timed_out' if isinstance(error,TimeoutError) else 'failed','error':str(error)}
    finally:
        if proc and proc.poll() is None:stop_native(proc);proc.wait(timeout=10)
        if reader:reader.join(timeout=2)
        if sampler:sampler.close();sampler=None
        progress.set_phase('cleanup');publish()
        try:cleanup(work,ROOT/'data/native-output',remove_output=result['status']!='completed')
        except OSError as error:result['cleanupWarning']=str(error)
        try:(work/'stdout.log').write_bytes(progress.transcript_tail())
        except OSError:pass
        if result['status']=='completed':progress.set_phase('complete')
        scratch_bytes=0;publish()
        result['wallSeconds']=time.monotonic()-started
        result.update(supervisorCpuSeconds=time.process_time()-cpu_started,telemetryFrames=sequence,nativeProgressUpdates=progress.native_updates)
        atomic_write(work/'runner-result.json',json.dumps(result))
    return 0 if result['status']=='completed' else 1

class ElevatedProcess:
    def __init__(self,handle):self.handle=handle
    def poll(self):
        from ctypes import wintypes as w
        kernel=ctypes.WinDLL('kernel32',use_last_error=True);kernel.GetExitCodeProcess.argtypes=[w.HANDLE,ctypes.POINTER(w.DWORD)]
        code=w.DWORD();kernel.GetExitCodeProcess(self.handle,ctypes.byref(code));return None if code.value==259 else code.value
    def close(self):
        from ctypes import wintypes as w
        kernel=ctypes.WinDLL('kernel32');kernel.CloseHandle.argtypes=[w.HANDLE];kernel.CloseHandle(self.handle)

def launch(request_path,elevate=False):
    args=[str(ROOT/'native_runner.py'),str(request_path)]
    if not elevate:return subprocess.Popen([sys.executable,*args],creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    from ctypes import wintypes as w
    class SHELLEXECUTEINFO(ctypes.Structure):
        _fields_=[('cbSize',w.DWORD),('fMask',ctypes.c_ulong),('hwnd',w.HWND),('lpVerb',w.LPCWSTR),('lpFile',w.LPCWSTR),('lpParameters',w.LPCWSTR),('lpDirectory',w.LPCWSTR),('nShow',ctypes.c_int),('hInstApp',w.HINSTANCE),('lpIDList',ctypes.c_void_p),('lpClass',w.LPCWSTR),('hkeyClass',w.HKEY),('dwHotKey',w.DWORD),('hIcon',w.HANDLE),('hProcess',w.HANDLE)]
    info=SHELLEXECUTEINFO();info.cbSize=ctypes.sizeof(info);info.fMask=0x40|0x100;info.lpVerb='runas';info.lpFile=sys.executable;info.lpParameters=subprocess.list2cmdline(args);info.lpDirectory=str(ROOT);info.nShow=0
    shell=ctypes.WinDLL('shell32',use_last_error=True);shell.ShellExecuteExW.argtypes=[ctypes.POINTER(SHELLEXECUTEINFO)]
    if not shell.ShellExecuteExW(ctypes.byref(info)):raise PermissionError('Windows administrator approval was cancelled. The existing digit cache is unchanged.')
    return ElevatedProcess(info.hProcess)

def run_batch(request_path):
    work=checked_job(Path(request_path).parent,ROOT/'data/native-output')
    request=json.loads(Path(request_path).read_text());jobs=request['jobs'];results=[]
    if not 1<=len(jobs)<=12:raise ValueError('Invalid benchmark batch size')
    for name in jobs:
        job=checked_job(Path(name).parent,ROOT/'data/native-output')
        item=json.loads((job/'request.json').read_text())
        if item['ownerPid']!=request['ownerPid']:raise ValueError('Benchmark job owner mismatch')
        if (work/'cancel').exists() or not owner_alive(int(request['ownerPid'])):break
        atomic_write(work/'batch-progress.json',json.dumps({'index':len(results),'total':len(jobs),'label':item.get('label','Native calculation')}))
        run(job/'request.json')
        results.append({'job':str(job),'result':json.loads((job/'runner-result.json').read_text())})
    atomic_write(work/'batch-result.json',json.dumps(results))
    return 0

if __name__=='__main__':
    request=Path(sys.argv[1]);data=json.loads(request.read_text())
    raise SystemExit(run_batch(request) if 'jobs' in data else run(request))
