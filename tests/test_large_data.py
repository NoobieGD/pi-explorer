import unittest,tempfile,random
from pathlib import Path
from unittest.mock import patch
from digit_store import DigitStore,PREFIX
from stream_search import search_sequence,search_shapes
import engine

class StoreTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.path=Path(self.folder.name)/'pi.txt'
    def tearDown(self):self.folder.cleanup()
    def test_native_prefix_raw_and_tail_views(self):
        for prefix in (b'',b'3.'):
            self.path.write_bytes(prefix+PREFIX+b'\n')
            data=DigitStore(self.path)
            try:
                self.assertEqual(len(data),50);self.assertEqual(data[:50],PREFIX)
                self.assertEqual(data.window(23,20)[0],PREFIX[23:43])
                self.assertEqual(data.window(40,20)[0],PREFIX[40:])
                self.assertEqual(data.window(0,100,'text')[0],engine.letters(PREFIX))
            finally:data.close()
    def test_sampled_tile_matches_independent_scalar_mapping(self):
        raw=PREFIX+b'0123456789'*100;self.path.write_bytes(b'3.'+raw);data=DigitStore(self.path)
        try:
            for mode,scheme,rule,alignment in [('digits','mod26','threshold',0),('colors','mod26','threshold',0),('binary','mod26','threshold',0),('binary','mod26','parity',0),('text','mod26','threshold',1),('text','ascii','threshold',0),('text','a1z26','threshold',0)]:
                step=(3 if scheme=='ascii' else 2) if mode=='text' else 1
                expected=[];total=(len(raw)-(alignment if mode=='text' else 0))//step
                for y in range(20):
                    for x in range(8):
                        index=(1+y*3)*19+2+x*2
                        if index>=total:expected.append(32);continue
                        at=index*step+(alignment if mode=='text' else 0);value=int(raw[at:at+step])
                        if mode=='text':value=65+value%26 if scheme=='mod26' else (64+value if 1<=value<=26 else 46) if scheme=='a1z26' else value if 32<=value<=126 else 46
                        elif mode=='binary':value=49 if (value%2 if rule=='parity' else value>=5) else 48
                        else:value+=48
                        expected.append(value)
                got,n=data.tile(19,1,2,20,8,3,2,mode,scheme,rule,alignment)
                self.assertEqual(got,bytes(expected));self.assertEqual(n,total)
        finally:data.close()
    def test_digit_and_text_search_cross_chunk_boundaries(self):
        n=2*1024*1024;raw=bytearray(PREFIX+b'0'*(n*2+100-len(PREFIX)))
        raw[n-4:n+5]=b'123456789';position=2*(n-1);raw[position:position+8]=b'01020304';self.path.write_bytes(raw)
        data=DigitStore(self.path)
        try:
            positions,capped,_=search_sequence(data,b'123456789');self.assertIn(n-4,positions);self.assertFalse(capped)
            positions,capped,_=search_sequence(data,b'BCDE','text');self.assertIn(n-1,positions);self.assertFalse(capped)
        finally:data.close()
    def test_shape_halo_and_global_row_alignment(self):
        block=2*1024*1024;p=block-4;raw=bytearray(PREFIX+b'0'*(block+100-len(PREFIX)))
        for offset in (0,1,7,8):raw[p+offset]=56
        self.path.write_bytes(raw);data=DigitStore(self.path)
        try:
            got,_=search_shapes(data,['11','11'],[7]);expected,_=engine.find_shapes(engine.binary(bytes(raw)),['11','11'],[7])
            self.assertEqual(got,expected);self.assertIn(p,[m['index'] for m in got])
        finally:data.close()
    def test_streamed_stats_equal_full_digit_counts(self):
        raw=PREFIX+b'0123456789'*500000;self.path.write_bytes(raw);data=DigitStore(self.path)
        try:
            result=engine.statistics(data)
            self.assertEqual(result['counts'],[raw.count(str(i).encode()) for i in range(10)])
            import hashlib
            self.assertEqual(result['sha256'],hashlib.sha256(raw).hexdigest())
        finally:data.close()
    def test_billion_requires_physical_memory_without_disabling_verification(self):
        with patch('engine.available_memory',return_value=512*1024**2):
            with self.assertRaises(MemoryError):engine.check_native_memory(1000000000)
        with patch('engine.available_memory',return_value=8*1024**3):
            self.assertGreater(engine.check_native_memory(1000000000)['estimatedBytes'],4*1024**3)

if __name__=='__main__':unittest.main()
