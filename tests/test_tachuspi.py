import json, struct, tempfile, unittest, os
from pathlib import Path
from unittest.mock import patch
import engine, resource_plan as r, tachuspi
from digit_store import DigitStore, PREFIX
from mpt_store import HEADER, TAG_OFFSET, tag_decimal_output
from stream_search import search_sequence, search_shapes

def fixture(path,raw):
    words=[int(raw[i:i+19].ljust(19,b'0')) for i in range(0,len(raw),19)]
    # Include unused low guard limbs and allocation padding, as native output does.
    limbs=[123,456]+list(reversed(words))+[3]
    allocated=len(limbs)+8
    header=HEADER.pack(b'MPT\x01FILE',len(limbs),allocated,2,0,0,1).ljust(4096,b'\0')
    path.write_bytes(header+struct.pack('<'+'Q'*allocated,*(limbs+[0]*8)))
    tag_decimal_output(path,len(raw))

class PackedTests(unittest.TestCase):
    def test_sparse_packed_file_beyond_two_gibibytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'large.mpt';count=5_500_000_009
            words=(count+18)//19+1
            with path.open('w+b') as f:
                if os.name=='nt':
                    import ctypes, msvcrt
                    from ctypes import wintypes as w
                    api=ctypes.WinDLL('kernel32',use_last_error=True)
                    api.DeviceIoControl.argtypes=[w.HANDLE,w.DWORD,ctypes.c_void_p,w.DWORD,ctypes.c_void_p,w.DWORD,ctypes.POINTER(w.DWORD),ctypes.c_void_p]
                    returned=w.DWORD()
                    if not api.DeviceIoControl(msvcrt.get_osfhandle(f.fileno()),0x900C4,None,0,None,0,ctypes.byref(returned),None):
                        self.skipTest('Filesystem does not support sparse test files')
                f.write(HEADER.pack(b'MPT\x01FILE',words,words,2,0,0,1))
                f.truncate(4096+words*8)
                f.seek(4096+(words-1)*8);f.write(struct.pack('<Q',3))
                for i in range(0,len(PREFIX),19):
                    f.seek(4096+(words-2-i//19)*8)
                    f.write(struct.pack('<Q',int(PREFIX[i:i+19].ljust(19,b'0'))))
            tag_decimal_output(path,count)
            store=DigitStore(path)
            try:
                self.assertGreater(path.stat().st_size,2*r.GIB)
                self.assertEqual(store[:len(PREFIX)],PREFIX)
                self.assertEqual(store[3_000_000_000:3_000_000_019],b'0'*19)
                self.assertEqual(store[-19:],b'0'*19)
                self.assertEqual(store.tile(200,15_000_000,0,1,3)[0],b'000')
            finally:store.close()

    def test_mpt_windows_encodings_tiles_searches_and_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);packed=root/'pi-4000.mpt';text=root/'plain.txt'
            raw=PREFIX+b'000001230000123456789'*157+b'0012'
            fixture(packed,raw);text.write_bytes(raw)
            a=DigitStore(packed);b=DigitStore(text)
            try:
                self.assertTrue(a.packed);self.assertEqual(len(a),len(raw))
                for start in [0,1,17,18,19,20,len(raw)-23]:self.assertEqual(a[start:start+83],b[start:start+83])
                self.assertEqual(a[-1],raw[-1])
                for mode,scheme,alignment in [('digits','mod26',0),('text','mod26',1),('text','a1z26',0),('text','ascii',2),('binary','mod26',0)]:
                    self.assertEqual(a.window(7,190,mode,scheme,'parity',alignment),b.window(7,190,mode,scheme,'parity',alignment))
                    self.assertEqual(a.tile(29,1,2,34,9,3,2,mode,scheme,'parity',alignment),b.tile(29,1,2,34,9,3,2,mode,scheme,'parity',alignment))
                self.assertEqual(search_sequence(a,b'0000123')[:2],search_sequence(b,b'0000123')[:2])
                self.assertEqual(search_shapes(a,['11','01'],[7,13]),search_shapes(b,['11','01'],[7,13]))
            finally:a.close();b.close()
            again=DigitStore(packed)
            try:self.assertEqual(again[:],raw)
            finally:again.close()

    def test_untagged_tampered_and_truncated_mpt_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pi.mpt';fixture(path,PREFIX*3);valid=path.read_bytes()
            for malformed in [valid[:TAG_OFFSET]+b'\0'*24+valid[TAG_OFFSET+24:],valid[:-8],valid[:TAG_OFFSET+8]+b'\0'*8+valid[TAG_OFFSET+16:]]:
                path.write_bytes(malformed)
                with self.assertRaises(ValueError):DigitStore(path)

    def test_trial_plan_and_cache_lookup_keep_real_limits(self):
        p=tachuspi.plan(62831853071,'.',800*r.MIB,mode='disk',free=276*r.GIB)
        self.assertLess(p['peakDiskBytes']+p['diskReserveBytes'],276*r.GIB)
        self.assertFalse(p['storageBoundVerified']);self.assertFalse(p['requiresElevation'])
        with self.assertRaises(OSError):tachuspi.plan(200000000000,'.',800*r.MIB,free=210*r.GIB)
        with self.assertRaises(MemoryError):tachuspi.plan(1000000,'.',350*r.MIB,free=10*r.GIB)
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pi-1000.mpt';path.touch()
            self.assertEqual(r.dataset_path(directory,1000),path)
            self.assertEqual(r.dataset_path(directory,1000,'mpt'),path)

    def test_native_phase_progress_and_verification_are_required(self):
        p=tachuspi.Progress(1000000)
        p.feed(b'Binary Splitting\r\n1M 2M 0 0 bs 25.0% 2\r')
        self.assertEqual(p.snapshot()['phaseProgress'],.25)
        p.feed(b'Final multiplication\nTotal time (base 10 result) = 0.2 s\n')
        self.assertFalse(p.verified)
        p.feed(b'Base conversion check\nTotal time (base 10 result) = 0.3 s\n')
        self.assertTrue(p.verified)

@unittest.skipUnless(tachuspi.EXE.exists(),'Official TachusPI personal installation required')
class NativeTests(unittest.TestCase):
    def test_actual_disk_worker_commits_packed_cache_and_checks_mpfr(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            (root/'request.json').write_text(json.dumps({'storageMode':'disk','memoryMiB':32}))
            engine.worker(100003,'tachuspi',root,request_name='request.json')
            path=root/'pi-100003.mpt'
            self.assertTrue(path.exists());self.assertFalse(path.with_suffix('.txt').exists())
            store=DigitStore(path)
            try:self.assertEqual(store[:].decode(),engine.compute_pi(100003,'mpfr'))
            finally:store.close()
            meta=json.loads(path.with_suffix('.json').read_text())
            self.assertEqual(meta['method'],'tachuspi');self.assertEqual(meta['format'],'tachuspi-mpt')
            self.assertTrue(meta['independentMpfrVerified'])
            self.assertFalse(list((root/'native-output').glob('*/swap')))

    def test_cancel_stops_native_and_removes_its_scratch(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=[]
            with self.assertRaises(InterruptedError):
                tachuspi.compute_file(25000000,root,options={'storageMode':'disk','memoryMiB':32},
                    cancelled=lambda:True,on_native_job=lambda path,plan:work.append(path),deadline=10)
            self.assertTrue(work)
            self.assertFalse((work[0]/'swap').exists())
            self.assertFalse((work[0]/'Pi - Dec.mpt').exists())

if __name__=='__main__':unittest.main()
