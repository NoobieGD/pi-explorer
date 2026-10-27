"""Small explicit disk-mode verification. Windows will ask to elevate the worker."""
import sys,json,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import engine,resource_plan
from digit_store import DigitStore
started=time.perf_counter()
path,info=engine.compute_ycruncher_file(1_000_000,ROOT/'data',options={'storageMode':'disk','memoryMiB':128},deadline=120)
store=DigitStore(path)
try:
    expected=engine.compute_pi(1_000_000,'mpfr')
    assert store[:len(store)].decode('ascii')==expected,'Independent MPFR comparison failed'
finally:store.close()
assert not (path.parent/'swap').exists(),'Scratch not removed'
result={'verified':True,'digits':1_000_000,'wallSeconds':time.perf_counter()-started,**info}
(ROOT/'benchmarks/disk-validation.json').write_text(json.dumps(result,indent=2))
resource_plan.cleanup(path.parent,ROOT/'data/native-output',remove_output=True)
print(json.dumps(result,indent=2))
