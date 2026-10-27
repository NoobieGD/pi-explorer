"""Bounded end-to-end disk-mode validation, never the user's large target."""
import sys, json, time, tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import engine
from digit_store import DigitStore
from stream_search import search_sequence

def main():
    started=time.perf_counter();source=DigitStore(ROOT/'data/pi-27182818284.txt')
    try:
        with tempfile.TemporaryDirectory(prefix='pi-tachuspi-') as folder:
            root=Path(folder);events=[]
            (root/'request.json').write_text(json.dumps({'storageMode':'disk','memoryMiB':32}))
            # More than the memory cap can retain: exercise actual disk arithmetic.
            engine.worker(25_000_000,'tachuspi',root,request_name='request.json')
            path=root/'pi-25000000.mpt';store=DigitStore(path)
            try:
                assert len(store)==25_000_000
                for lo in range(0,len(store),1_000_000):
                    assert store[lo:lo+1_000_000]==source[lo:lo+1_000_000]
                assert search_sequence(store,b'12345')[0][0]==49701
                meta=json.loads(path.with_suffix('.json').read_text())
                # Close/reopen to verify restart cache semantics and exact count.
                size=path.stat().st_size
            finally:store.close()
            reopened=DigitStore(path)
            try:assert reopened[-73:]==source[25_000_000-73:25_000_000]
            finally:reopened.close()
            progress=json.loads((root/'compute-progress.json').read_text())
            assert progress['progress']==1
            assert not list((root/'native-output').glob('*/swap'))
            report={'verified':True,'digits':25_000_000,'packedBytes':size,
                    'nativeSeconds':meta['nativeSeconds'],'memoryOptionMiB':32,
                    'wallSeconds':time.perf_counter()-started,'exactDatasetComparison':True,
                    'packedSearchVerified':True,'restartVerified':True,'scratchRemoved':True,
                    'largeTargetComputed':False}
            (ROOT/'benchmarks/tachuspi-integrated-validation.json').write_text(json.dumps(report,indent=2))
            print(json.dumps(report,indent=2))
    finally:source.close()

if __name__=='__main__':main()
