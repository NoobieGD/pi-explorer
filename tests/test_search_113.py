import sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import stream_search,fast_search
from digit_store import DigitStore,PREFIX,transform
class Search113Tests(unittest.TestCase):
 def test_mapped_paths_preserve_all_encodings_alignment_and_overlap(self):
  raw=PREFIX+b'0123456789'*200+b'065066067'*5+b'010203'*8
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'pi.txt';p.write_bytes(b'3.'+raw+b'\n');s=DigitStore(p)
   try:
    with patch.object(fast_search,'available',return_value=False):
     for mode,scheme,q in [('digits','mod26',b'010'),('text','ascii',b'ABC'),('text','ascii',b'.'),('text','a1z26',b'ABC'),('text','a1z26',b'.'),('text','mod26',b'ABC')]:
      for alignment in range(3 if scheme=='ascii' else 2 if mode=='text' else 1):
       data=transform(raw,mode,scheme,alignment=alignment);expected=[];start=0
       while True:
        at=data.find(q,start)
        if at<0:break
        expected.append(at);start=at+1
       fast_search.clear_cache();actual=stream_search.search_sequence(s,q,mode,scheme,alignment,10000)
       self.assertEqual(actual[:2],(expected,False),(mode,scheme,alignment))
   finally:s.close()
 def test_cache_cancellation_and_result_limits(self):
  with tempfile.TemporaryDirectory() as tmp:
   p=Path(tmp)/'pi.txt';p.write_bytes(PREFIX+b'11111');s=DigitStore(p)
   try:
    fast_search.clear_cache();a={};b={}
    with patch.object(fast_search,'available',return_value=False):
     first=stream_search.search_sequence(s,b'11',limit=2,metrics=a)
     again=stream_search.search_sequence(s,b'11',limit=2,metrics=b)
     self.assertEqual(first,again);self.assertTrue(first[1]);self.assertTrue(b['cacheHit'])
     with self.assertRaises(InterruptedError):stream_search.search_sequence(s,b'11',limit=2,cancelled=lambda:True)
   finally:s.close()
 def test_mapped_query_crosses_task_boundary_once(self):
  with tempfile.TemporaryDirectory() as tmp:
   raw=bytearray(PREFIX+b'0'*(16*1024*1024+100));at=16*1024*1024-3;raw[at:at+8]=b'12345678'
   p=Path(tmp)/'pi.txt';p.write_bytes(raw);s=DigitStore(p)
   try:
    with patch.object(fast_search,'available',return_value=False):self.assertEqual(stream_search.search_sequence(s,b'12345678')[0],[at])
   finally:s.close()
