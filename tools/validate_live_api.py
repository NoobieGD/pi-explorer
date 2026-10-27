"""Fresh RAM calculation and measurement of the actual localhost live feed."""
import time,json,urllib.request,sys,statistics
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
from digit_store import DigitStore
BASE='http://127.0.0.1:31415/api/'
def get():return json.load(urllib.request.urlopen(BASE+'status'))
def post(route,payload):
    token=get()['token'];request=urllib.request.Request(BASE+route,json.dumps(payload).encode(),{'Content-Type':'application/json','X-Pi-Token':token})
    return json.load(urllib.request.urlopen(request))
initial=get()
if initial['busy']:raise RuntimeError('Preserving the existing calculation; validation did not start.')
count=50_000_000
post('compute',{'count':count,'method':'ycruncher','storageMode':'ram','force':True})
print('Fresh 50M RAM calculation started; measuring the live API.',flush=True)
started=time.perf_counter();frames=[];requests=[];seen=set()
while True:
    request_started=time.perf_counter();state=get();requests.append(time.perf_counter()-request_started)
    live=state.get('telemetry')
    if live and live['sequence'] not in seen:
        seen.add(live['sequence']);frames.append(live)
    if not state['busy']:
        if state.get('error'):raise RuntimeError(state['error'])
        break
    if time.perf_counter()-started>120:post('cancel',{});raise TimeoutError('Live validation exceeded its bound')
    time.sleep(.08)
mapped=DigitStore(ROOT/'data'/f'pi-{count}.txt');reference=DigitStore(ROOT/'data'/f"pi-{initial['count']}.txt")
try:
    assert all(mapped[i:min(count,i+4194304)]==reference[i:min(count,i+4194304)] for i in range(0,count,4194304))
finally:mapped.close();reference.close()
assert any(f['phase']=='series' and f.get('phaseProgress') is not None for f in frames),'No native summation percentages'
assert any(f.get('cpuPercent',0)>0 for f in frames),'No CPU activity'
assert len(frames)>5,'Too few live snapshots'
ages=sorted(f['ageSeconds'] for f in frames)
record={'digits':count,'cold':True,'verifiedAgainstPreviousCache':True,'wallSeconds':time.perf_counter()-started,'uniqueSnapshots':len(frames),'nativePhases':sorted(set(f['phase'] for f in frames)),'snapshotAgeP95Seconds':ages[min(len(ages)-1,int(len(ages)*.95))],'medianStatusRequestSeconds':statistics.median(requests),'frames':frames}
(ROOT/'benchmarks/live-progress.json').write_text(json.dumps(record,indent=2))
print(json.dumps({k:v for k,v in record.items() if k!='frames'},indent=2),flush=True)
if not get()['busy']:post('compute',{'count':initial['count'],'method':'auto','force':False})
