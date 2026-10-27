"""Bounded 1M-digit verification of the complete reduced/YCD native pipeline."""
from pathlib import Path
import sys,json,time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import engine,resource_plan
from digit_store import DigitStore
started=time.perf_counter()
path,info=engine.compute_ycruncher_file(1000000,ROOT/'data',options={'lowDisk':True,'storageMode':'ram'},deadline=60)
store=DigitStore(path)
try:
    assert getattr(store,'packed',False)
    assert store[:len(store)].decode()==engine.compute_pi(1000000,'mpfr')
    report={'verified':True,'digits':len(store),'packedBytes':path.stat().st_size,'expectedTextBytes':len(store)+2,'wallSeconds':time.perf_counter()-started,**info}
finally:store.close()
assert not (path.parent/'swap').exists()
(ROOT/'benchmarks/low-disk-validation.json').write_text(json.dumps(report,indent=2))
resource_plan.cleanup(path.parent,ROOT/'data/native-output',remove_output=True)
print(json.dumps({key:report[key] for key in ('verified','digits','packedBytes','expectedTextBytes','wallSeconds')},indent=2))
