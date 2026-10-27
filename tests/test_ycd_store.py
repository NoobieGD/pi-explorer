import unittest,tempfile,struct
from pathlib import Path
from digit_store import DigitStore,PREFIX
from stream_search import search_sequence,search_shapes
import resource_plan as r,native_runner,engine
from unittest.mock import patch
import json

def fixture(path,raw):
    header=f'#Compressed Digit File\r\nFileVersion:\t1.1.0\r\nBase:\t10\r\nFirstDigits:\t3.14159\r\nTotalDigits:\t0\r\nBlocksize:\t{len(raw)}\r\nBlockID:\t0\r\nEndHeader\r\n\0'.encode()
    with path.open('wb') as f:
        f.write(header)
        for at in range(0,len(raw),19):f.write(struct.pack('<Q',int(raw[at:at+19].ljust(19,b'0'))))

class YcdTests(unittest.TestCase):
    def test_unaligned_windows_tiles_and_searches_match_text(self):
        raw=PREFIX+b'0000000000000000000123456789'*400
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);packed=root/'pi.ycd';plain=root/'pi.txt';fixture(packed,raw);plain.write_bytes(raw)
            a=DigitStore(packed);b=DigitStore(plain)
            try:
                self.assertLess(packed.stat().st_size,len(raw)//2)
                for start in (0,1,17,18,19,20,len(raw)-25):self.assertEqual(a[start:start+53],b[start:start+53])
                for mode,scheme,alignment in [('digits','mod26',0),('text','mod26',1),('text','a1z26',0),('text','ascii',2),('binary','mod26',0)]:
                    self.assertEqual(a.window(7,100,mode,scheme,alignment=alignment),b.window(7,100,mode,scheme,alignment=alignment))
                    self.assertEqual(a.tile(23,1,2,30,9,3,2,mode,scheme,'parity',alignment),b.tile(23,1,2,30,9,3,2,mode,scheme,'parity',alignment))
                self.assertEqual(search_sequence(a,b'123456789')[:2],search_sequence(b,b'123456789')[:2])
                self.assertEqual(search_sequence(a,b'BC','text')[:2],search_sequence(b,b'BC','text')[:2])
                self.assertEqual(search_shapes(a,['11','01'],[7,13]),search_shapes(b,['11','01'],[7,13]))
                self.assertEqual(engine.statistics(a)['sha256'],engine.statistics(b)['sha256'])
            finally:a.close();b.close()
    def test_truncation_and_partial_sets_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'x.ycd';fixture(path,PREFIX)
            data=path.read_bytes();path.write_bytes(data[:-8])
            with self.assertRaisesRegex(ValueError,'Truncated'):DigitStore(path)
            path.write_bytes(data.replace(b'BlockID:\t0',b'BlockID:\t1'))
            with self.assertRaisesRegex(ValueError,'split set'):DigitStore(path)
    def test_low_disk_is_real_and_does_not_bypass_available_storage(self):
        n=62831853071
        normal=r.plan(n,'.',512*r.MIB,free=1000*r.GIB)
        low=r.plan(n,'.',512*r.MIB,free=1000*r.GIB,low_disk=True)
        self.assertLess(low['peakDiskBytes'],normal['peakDiskBytes']/2)
        self.assertLess(low['outputBytes'],25*r.GIB)
        with self.assertRaises(OSError):r.plan(n,'.',512*r.MIB,free=276*r.GIB,low_disk=True)
        with tempfile.TemporaryDirectory() as directory:
            cfg=native_runner.configuration(Path(directory),1000000,{'lowDisk':True},low).read_text()
            self.assertIn('Algorithm : "chudnovsky-reduced"',cfg)
            self.assertIn('Framework : "ycd"',cfg)
            self.assertIn('OutputVerify : true',cfg);self.assertIn('Checksums : true',cfg)
    def test_cache_path_recognizes_saved_packed_output(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'pi-1000.ycd';path.touch()
            self.assertEqual(r.dataset_path(directory,1000),path)
    def test_auto_falls_back_to_reduced_packed_when_only_that_fits(self):
        with patch.object(engine,'available_memory',return_value=512*r.MIB),patch.object(r.shutil,'disk_usage',return_value=type('Disk',(),{'free':60*r.GIB})()):
            plan=engine.computation_plan(10000000000,'.','auto')
            self.assertTrue(plan['lowDisk']);self.assertEqual(plan['preferredMethod'],'ycruncher-low')
    def test_worker_commits_packed_file_without_a_text_copy(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);job=root/'source';job.mkdir();output=job/'Pi - Dec - 0.ycd';raw=PREFIX+b'0123456789'*100;fixture(output,raw)
            with patch.object(engine,'compute_ycruncher_file',return_value=(output,{})) as native:
                engine.worker(len(raw),'ycruncher-low',root)
            self.assertTrue(native.call_args.args[3]['lowDisk'])
            self.assertTrue((root/f'pi-{len(raw)}.ycd').exists());self.assertFalse((root/f'pi-{len(raw)}.txt').exists())
            meta=json.loads((root/f'pi-{len(raw)}.json').read_text());self.assertEqual(meta['format'],'ycd-packed');self.assertEqual(meta['method'],'ycruncher-low')

if __name__=='__main__':unittest.main()
