"""Conservative RAM/disk plans and cleanup restricted to owned scratch jobs."""
import json,os,re,shutil,time,stat
from pathlib import Path

MIB=1024**2
GIB=1024**3
DISK_RESERVE=2*GIB
CACHE_LIMIT=2*GIB

def digit_count(value):
    if isinstance(value,bool) or not isinstance(value,(int,str)) or (isinstance(value,str) and not re.fullmatch(r'[0-9]+',value.strip())):
        raise ValueError('Enter a positive whole number of decimal places')
    count=int(value)
    if count<1:raise ValueError('Enter a positive whole number of decimal places')
    return count

def estimate_ram(count):return (count*485+99)//100+40*MIB

def ram_budget(available,memory_mib=0):
    budget=max(0,(available-320*MIB)*4//5)//MIB*MIB
    return min(budget,int(memory_mib)*MIB) if memory_mib else budget

def gib_text(size):
    whole,fraction=divmod(size,GIB)
    return f'{whole:,}.{fraction*100//GIB:02d}'

def dataset_path(folder,count,packed=False,constant='pi'):
    from constants import identify
    constant=identify(constant)
    folder=Path(folder);preferred=folder/f'{constant}-{count}.{ "mpt" if packed=="mpt" else "ycd" if packed else "txt"}'
    if preferred.exists() or packed:return preferred
    alternate=folder/f'{constant}-{count}.ycd'
    if alternate.exists():return alternate
    alternate=folder/f'{constant}-{count}.mpt'
    return alternate if alternate.exists() else preferred

def plan(count,folder,available,method='auto',mode='auto',memory_mib=0,free=None,low_disk=False,constant='pi'):
    count=digit_count(count);folder=Path(folder).resolve()
    if mode not in ('auto','ram','disk'):raise ValueError('Unknown memory strategy')
    if int(memory_mib)<0:raise ValueError('RAM limit must be 0 (automatic) or a positive number of MiB')
    # Leave headroom for the GUI, native I/O buffers and other running apps.
    budget=ram_budget(available,memory_mib)
    native=method in ('auto','ycruncher')
    required=estimate_ram(count) if native else count*14+40*MIB
    if not native and mode=='disk':raise ValueError('Choose Auto or y-cruncher to use disk-backed blocks.')
    disk=native and (mode=='disk' or (mode=='auto' and required>budget))
    if not native and required>budget:raise MemoryError('This comparison engine does not support disk blocks. Choose Auto for a RAM-aware calculation.')
    if native and mode=='ram' and required>budget:raise MemoryError('The RAM-only calculation exceeds the safe memory budget. Choose Automatic or Disk-backed blocks.')
    if disk and budget<96*MIB:raise MemoryError('Less than 96 MiB of safe working RAM is available. The current dataset remains usable; generation can start when a little more RAM is available.')
    output=((count+18)//19)*8+MIB if low_disk else count+2
    # The reduced formula's native dry-run reports 269 GiB scratch at 62.83B.
    # Use 4.65 bytes/digit plus fixed headroom, not an optimistic peak guess.
    scratch=((count*465+99)//100+128*MIB if low_disk and constant=='pi' else int(count*10+128*MIB)) if disk else 0
    disk_needed=output+scratch
    free=shutil.disk_usage(folder).free if free is None else free
    if free<disk_needed+DISK_RESERVE:raise OSError(f'Not enough free disk space: {"reduced Chudnovsky + packed YCD" if low_disk and constant=="pi" else "packed native output" if low_disk else "this run"} needs up to {gib_text(disk_needed)} GiB for output and temporary blocks, plus the 2 GiB reserve; {gib_text(free)} GiB is available.')
    return {'digits':count,'constant':constant,'reducedFormula':low_disk and constant=='pi','mode':'disk' if disk else 'ram','availableBytes':available,'estimatedBytes':required,
            'ramBudgetBytes':budget,'scratchLimitBytes':scratch,'outputBytes':output,'peakDiskBytes':disk_needed,
            'freeDiskBytes':free,'diskReserveBytes':DISK_RESERVE,'requiresElevation':disk and os.name=='nt',
            'memoryMiB':int(memory_mib),'requestedMode':mode,'lowDisk':low_disk,'outputFormat':'ycd' if low_disk else 'text'}

def checked_job(work,root):
    work=Path(work).resolve();root=Path(root).resolve()
    if work.parent!=root or not re.fullmatch(r'run-\d+-[a-f0-9]{8}',work.name):raise ValueError('Scratch path is outside the owned job directory')
    return work

def cleanup(work,root,remove_output=False):
    work=checked_job(work,root)
    scratch=work/'swap'
    if scratch.exists():
        if scratch.is_symlink() or not scratch.resolve().is_relative_to(work):raise ValueError('Scratch path is not contained in its job')
        for attempt in range(24):
            try:shutil.rmtree(scratch);break
            except FileNotFoundError:
                if not scratch.exists():break
            except PermissionError:
                if attempt==23:raise
            time.sleep(.05)
        else:
            if scratch.exists():raise OSError('Native scratch cleanup did not finish')
    if remove_output:
        for output in list(work.glob('*Dec*.txt'))+list(work.glob('*Dec*.ycd'))+list(work.glob('*Dec*.mpt')):
            if output.is_file() and not output.is_symlink():output.unlink()
    for temp in work.glob('y-cruncher Checkpoint*.txt'):
        if temp.is_file() and not temp.is_symlink():temp.unlink()

def job_bytes(work):
    total=0
    for path in Path(work).rglob('*'):
        try:
            info=path.stat(follow_symlinks=False)
            if stat.S_ISREG(info.st_mode):total+=info.st_size
        except (FileNotFoundError,PermissionError):pass
    return total

def prune_cache(folder,keep=(),quota=CACHE_LIMIT):
    folder=Path(folder).resolve();entries=[]
    from constants import CONSTANTS
    for path in (p for constant in CONSTANTS for suffix in ('txt','ycd','mpt') for p in folder.glob(f'{constant}-*.{suffix}')):
        try:
            if path.is_symlink() or not re.fullmatch(r'(?:'+'|'.join(CONSTANTS)+r')-\d+\.(?:txt|ycd|mpt)',path.name):continue
            meta=path.with_suffix('.json');info=json.loads(meta.read_text())
            if info.get('cacheManaged') is not True:continue
            # Large completed calculations are persistent datasets. Changing
            # constants must not evict a dataset bigger than the cache budget.
            if path.stat().st_size>quota:continue
            entries.append((path.stat().st_mtime_ns,path,path.stat().st_size))
        except (OSError,ValueError):continue
    total=sum(item[2] for item in entries)
    for _,path,size in sorted(entries):
        if total<=quota:break
        if path.name in keep:continue
        try:path.unlink();total-=size;path.with_suffix('.json').unlink(missing_ok=True)
        except OSError:pass
    return total

def cleanup_abandoned(folder):
    """Only new, explicitly owned scratch jobs; never digit caches or other files."""
    root=Path(folder).resolve()/'native-output'
    if not root.exists():return
    for work in root.glob('run-*'):
        marker=work/'job.json'
        try:
            meta=json.loads(marker.read_text())
            if meta.get('owner')!='Pi Explorer scratch v1':continue
            from native_runner import owner_alive
            if owner_alive(int(meta.get('ownerPid',0))):continue
            if (work/'runner-result.json').exists() or time.time()-marker.stat().st_mtime>30:
                cleanup(work,root,remove_output=True)
        except (OSError,ValueError):pass
