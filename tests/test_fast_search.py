import random,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import fast_search
from digit_store import DigitStore,PREFIX,transform

@unittest.skipUnless(fast_search.available(),'Native scanner unavailable')
class NativeSearchTests(unittest.TestCase):
    def setUp(self):
        self.folder=tempfile.TemporaryDirectory();self.path=Path(self.folder.name)/'pi.txt'
        self.store=None;fast_search.clear_cache()
    def tearDown(self):
        if self.store:self.store.close()
        self.folder.cleanup()
    def make(self,raw,native=True):
        if self.store:self.store.close()
        self.path.write_bytes((b'3.' if native else b'')+raw)
        self.store=DigitStore(self.path);return self.store
    def expected(self,data,q,cap=300):
        out=[];at=0
        while len(out)<=cap:
            at=data.find(q,at)
            if at<0:break
            out.append(at);at+=1
        return out[:cap],len(out)>cap
    def test_scalar_and_simd_all_encodings_and_alignments(self):
        rng=random.Random(976);raw=PREFIX+bytes(rng.randrange(48,58) for _ in range(12000))
        store=self.make(raw)
        for mode,scheme in [('digits','mod26'),('text','mod26'),('text','a1z26'),('text','ascii')]:
            step=3 if scheme=='ascii' else 2 if mode=='text' else 1
            for alignment in range(step):
                data=transform(raw,mode,scheme,alignment=alignment)
                for length in (1,2,3,4,7,16,33,180,2048):
                    for at in (0,17,max(0,len(data)-length)):
                        q=data[at:at+length]
                        for vector in (False,True):
                            found,capped,_=fast_search.sequence(store,q,mode,scheme,alignment,use_cache=False,vector=vector)
                            self.assertEqual((found,capped),self.expected(data,q),(mode,scheme,alignment,length,at,vector))
    def test_overlaps_limit_exactly_and_one_more(self):
        for runs in (301,302):
            raw=PREFIX+b'0'*runs;store=self.make(raw,False)
            result=fast_search.sequence(store,b'00',use_cache=False)
            self.assertEqual(result[:2],self.expected(raw,b'00'))
    def test_parallel_chunk_halo_and_order(self):
        chunk=16*1024*1024;raw=bytearray(PREFIX+b'0'*(chunk*2+101-len(PREFIX)))
        q=b'123456789876543210';places=[chunk-7,chunk+27,2*chunk-7]
        for at in places:raw[at:at+len(q)]=q
        store=self.make(raw);found,capped,_=fast_search.sequence(store,q,use_cache=False,threads=8)
        self.assertEqual(found,places);self.assertFalse(capped)
    def test_cache_is_encoding_alignment_and_file_specific(self):
        raw=PREFIX+b'12345678'*100;store=self.make(raw)
        first={};fast_search.sequence(store,b'12345678',metrics=first)
        second={};fast_search.sequence(store,b'12345678',metrics=second)
        self.assertFalse(first['cacheHit']);self.assertTrue(second['cacheHit'])
        store=self.make(PREFIX+b'87654321'*100)
        third={};found,_,_=fast_search.sequence(store,b'12345678',metrics=third)
        self.assertFalse(third['cacheHit']);self.assertEqual(found,[])
    def test_cancellation_releases_mapping(self):
        store=self.make(PREFIX+b'0'*5000000);calls=0
        def cancel():
            nonlocal calls
            calls+=1;return calls>2
        with self.assertRaises(InterruptedError):fast_search.sequence(store,b'99999',cancelled=cancel,use_cache=False)
        store.close();self.assertTrue(store.mapping.closed)
    def test_invalid_encoding_queries_are_empty(self):
        store=self.make(PREFIX)
        for scheme,q in [('mod26',b'.'),('a1z26',b'!'),('ascii',b'\xff')]:
            self.assertEqual(fast_search.sequence(store,q,'text',scheme)[:2],([],False))
    def test_unique_text_encoding_fast_path_including_last_character(self):
        for scheme,q in [('a1z26',b'PIEXPLORER'),('ascii',b'HelloWorld!')]:
            step=3 if scheme=='ascii' else 2
            encoded=b''.join(f'{v if step==3 else v-64:0{step}d}'.encode() for v in q)
            for alignment in range(step):
                # Align a known word after the required real pi prefix, at EOF.
                padding=(alignment-len(PREFIX))%step
                raw=PREFIX+b'9'*padding+encoded;store=self.make(raw)
                data=transform(raw,'text',scheme,alignment=alignment)
                result=fast_search.sequence(store,q,'text',scheme,alignment,use_cache=False)
                self.assertEqual(result[:2],self.expected(data,q))
    def test_shapes_match_independent_scalar_with_wildcards_and_row_edges(self):
        rng=random.Random(12);raw=PREFIX+bytes(rng.randrange(48,58) for _ in range(9000));store=self.make(raw)
        for rows in (['101','0?1','110'],['11','11'],['?1?']):
            for rule in ('threshold','parity'):
                w=len(rows[0]);h=len(rows);expected=[]
                for width in (7,11,17):
                    for at in range(len(raw)-(h-1)*width-w+1):
                        if at%width+w>width:continue
                        if all(ch=='?' or int(ch)==((raw[at+y*width+x]-48)%2 if rule=='parity' else raw[at+y*width+x]>=53) for y,row in enumerate(rows) for x,ch in enumerate(row)):
                            expected.append({'index':at,'position':at+1,'width':width,'height':h,'shapeWidth':w})
                expected.sort(key=lambda m:(m['index'],m['width']))
                found,capped=fast_search.shapes(store,rows,[7,11,17],rule,use_cache=False)
                self.assertEqual(found,expected[:60]);self.assertEqual(capped,len(expected)>60)

if __name__=='__main__':unittest.main()
