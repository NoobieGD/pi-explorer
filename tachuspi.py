"""Optional personal-install TachusPI engine, bounded jobs and packed output."""
import json, os, re, secrets, shutil, subprocess, threading, time
from pathlib import Path
import resource_plan as resources
from storage import atomic_write
from live_progress import NativeProgress, ProcessSampler
from mpt_store import tag_decimal_output

ROOT=Path(__file__).resolve().parent
EXE=ROOT/'vendor/tachuspi/tpi.exe'
MAX_NATIVE_DIGITS=2_700_000_000_000
GUARD_DIGITS=64  # Native base conversion can round down to a whole limb.

def plan(count,folder,available,mode='auto',memory_mib=0,free=None):
    count=resources.digit_count(count);folder=Path(folder).resolve()
    if count+GUARD_DIGITS>MAX_NATIVE_DIGITS:raise ValueError('This TachusPI release supports about 2.7 trillion digits including guard digits; other engines remain available.')
    if mode not in ('auto','ram','disk'):raise ValueError('Unknown memory strategy')
    if int(memory_mib)<0:raise ValueError('RAM limit cannot be negative')
    if not EXE.is_file():raise FileNotFoundError('TachusPI is not installed. Run tools/install_tachuspi.py with the bundled Python.')
    budget=resources.ram_budget(available,memory_mib)
    if budget<32*resources.MIB:raise MemoryError('TachusPI needs at least 32 MiB of safe working RAM.')
    required=count*7+64*resources.MIB
    disk=mode=='disk' or (mode=='auto' and required>budget)
    if mode=='ram' and required>budget:raise MemoryError('TachusPI RAM-only estimate exceeds the budget. Select Automatic or Disk-backed blocks.')
    output=((count+18)//19+1024)*8+4096
    # 25M/32MiB test: ~4.012 bytes/digit native peak. 4.2 plus fixed
    # headroom is a trial allocation budget, NOT a proven asymptotic bound.
    scratch=(count*42+9)//10+128*resources.MIB if disk else 0
    peak=output+scratch
    free=shutil.disk_usage(folder).free if free is None else free
    if free<peak+resources.DISK_RESERVE:
        raise OSError(f'TachusPI trial budget needs {resources.gib_text(peak)} GiB plus 2 GiB reserve; {resources.gib_text(free)} GiB is available. Large-run completion is not verified.')
    return {'digits':count,'method':'tachuspi','mode':'disk' if disk else 'ram',
            'availableBytes':available,'estimatedBytes':required,'ramBudgetBytes':budget,
            'memoryMiB':int(memory_mib),'requestedMode':mode,'scratchLimitBytes':scratch,
            'outputBytes':output,'peakDiskBytes':peak,'freeDiskBytes':free,
            'diskReserveBytes':resources.DISK_RESERVE,'requiresElevation':False,
            'outputFormat':'mpt','packedOutput':True,'launchable':True,
            'experimental':True,'storageBoundVerified':False,
            'publishedWorkingEstimateBytes':(count*27+9)//10,
            'message':'Bounded trial budget based on small tests; full-size completion is not verified. Slower than y-cruncher; saved digits stay packed.'}

class Progress(NativeProgress):
    def __init__(self,count):
        super().__init__(count);self.base_check=False;self.decimal_done=False
    def _line(self,line,final=False):
        line=line.strip()
        for marker,phase in [('Base conversion check','base_verify'),('Base conversion','convert'),
            ('Writing result','write'),('Final multiplication','multiply'),('Binary Splitting','series'),
            ('Compute P, Q','series'),('Division','divide'),('Sqrt','sqrt')]:
            if line.startswith(marker):self._phase(phase);break
        if self.phase=='series':
            percent=re.search(r'\bbs\s+([\d.]+)%',line)
            if percent:
                self.percent=min(1,float(percent[1])/100);self.last_native=time.monotonic();self.native_updates+=1
        if line.startswith('Base conversion check'):self.base_check=True
        if line.startswith('Total time (base 10 result)'):
            self.decimal_done=True;self.total_time=True
            self.verified=self.base_check

def compute_file(count,folder,progress=None,options=None,cancelled=None,on_native_job=None,on_telemetry=None,deadline=None):
    import engine
    from native_runner import stop_native
    from digit_store import DigitStore
    options=options or {};folder=Path(folder).resolve()
    admission=plan(count,folder,engine.available_memory(),options.get('storageMode','auto'),options.get('memoryMiB',0))
    work=folder/'native-output'/f'run-{count}-{secrets.token_hex(4)}';work.mkdir(parents=True)
    atomic_write(work/'job.json',json.dumps({'owner':'Pi Explorer scratch v1','ownerPid':os.getpid(),'engine':'tachuspi'}))
    swap=work/'swap';swap.mkdir();output=work/'Pi - Dec.mpt';logfile=work/'console.log'
    native=Progress(count);proc=None;reader=None;sampler=None;success=False
    started=time.monotonic();last_publish=last_disk=0;disk_bytes=0;sequence=0
    command=[str(EXE),'-T',str(min(8,os.cpu_count() or 1)),'-m',str(admission['ramBudgetBytes']),
             '-d',str(max(admission['scratchLimitBytes'],admission['outputBytes']+64*resources.MIB)),
             '-p',str(swap),'-f','bin','-o',str(swap/'decimal.mpt'),'-c',str(count+GUARD_DIGITS)]
    try:
        if on_native_job:on_native_job(work,admission)
        proc=subprocess.Popen(command,cwd=work,stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,
                              creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        sampler=ProcessSampler(proc.pid)
        def consume():
            # Keep only a bounded transcript; live phase parsing is incremental.
            while data:=proc.stdout.read1(8192):native.feed(data)
            native.finish()
        reader=threading.Thread(target=consume,daemon=True);reader.start()
        while proc.poll() is None:
            now=time.monotonic()
            if cancelled and cancelled():raise InterruptedError('Calculation cancelled')
            if deadline and now-started>deadline:raise TimeoutError('TachusPI test deadline exceeded')
            if now-last_disk>.25:
                disk_bytes=resources.job_bytes(work);last_disk=now
                if shutil.disk_usage(work).free<admission['diskReserveBytes']:raise OSError('Stopped to preserve 2 GiB of free disk space')
                limit=admission['peakDiskBytes'] if admission['mode']=='disk' else admission['outputBytes']+128*resources.MIB
                if disk_bytes>limit:raise OSError('TachusPI exceeded its trial disk budget. The previous dataset is unchanged.')
            if now-last_publish>.25:
                sequence+=1
                snapshot=native.snapshot();snapshot.update(sampler.sample(),sequence=sequence,nativeJob=work.name,scratchBytes=disk_bytes,mode=admission['mode'],engine='tachuspi')
                try:atomic_write(work/'telemetry.json',json.dumps(snapshot),retries=1)
                except OSError:pass  # A transient UI read lock must not fail arithmetic.
                if on_telemetry:on_telemetry(snapshot)
                elif progress:progress(snapshot['overallEstimate'],'TachusPI · '+snapshot['phaseLabel'])
                last_publish=now
            time.sleep(.05)
        reader.join(timeout=5)
        if reader.is_alive():raise RuntimeError('TachusPI output stream did not close')
        if proc.returncode!=0 or not native.verified or not native.decimal_done:
            raise ArithmeticError('TachusPI did not finish its multiplication/base-conversion checks. '+native.transcript_tail().decode(errors='replace')[-700:])
        if cancelled and cancelled():raise InterruptedError('Calculation cancelled')
        result=swap/'decimal.mpt'
        tag_decimal_output(result,count)
        store=DigitStore(result)
        try:
            if len(store)!=count:raise ArithmeticError('TachusPI output length mismatch')
            if count<=1_000_000 and store[:count].decode()!=engine.compute_pi(count,'mpfr'):
                raise ArithmeticError('TachusPI output disagrees with independent MPFR')
        finally:store.close()
        # Same-volume rename publishes packed data without a second full copy.
        os.replace(result,output);success=True
        log=native.transcript_tail().decode(errors='replace')
        timing=re.search(r'Total time \(base 10 result\) = ([\d.]+)',log)
        return output,{'nativeSeconds':float(timing[1]) if timing else None,'resourcePlan':admission,
                       'log':str(logfile),'nativeChecks':True,'independentMpfrVerified':count<=1_000_000,
                       'options':options,'nativeWallSeconds':time.monotonic()-started}
    finally:
        if proc and proc.poll() is None:stop_native(proc);proc.wait(timeout=10)
        if reader:reader.join(timeout=5)
        if sampler:sampler.close()
        if proc and proc.stdout:proc.stdout.close()
        logfile.write_bytes(native.transcript_tail())
        resources.cleanup(work,folder/'native-output',remove_output=not success)
