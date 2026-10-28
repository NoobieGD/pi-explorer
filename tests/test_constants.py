import sys,json,tempfile,unittest,struct,http.client,threading
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import constants,engine,resource_plan,native_runner,server
from digit_store import DigitStore,equal_files

class ConstantPrecisionTests(unittest.TestCase):
    def test_exact_algorithms_match_directed_mpfr_and_prefixes(self):
        for name,spec in constants.CONSTANTS.items():
            for count in (1,2,17,49,50,99,1000,10000):
                exact=engine.compute_constant(count,name)
                self.assertEqual(len(exact),count,(name,count))
                self.assertTrue(exact.startswith(spec['prefix'][:min(50,count)]))
                self.assertEqual(exact,engine.compute_constant(count,name,'mpfr'),(name,count))
    def test_invalid_identity_precision_and_pi_only_engines(self):
        for name in ('../pi','euler-gamma','unknown',None):
            with self.assertRaises(ValueError):engine.compute_constant(100,name)
        for count in (0,-1,True,1.5):
            with self.assertRaises(ValueError):engine.compute_constant(count,'sqrt2')
        for method in ('tachuspi','compact'):
            with self.assertRaises(ValueError):engine.computation_plan(100,method=method,constant='e')
    def test_native_auto_packs_other_constants_without_using_pis_reduced_formula(self):
        executable=type('AvailableNative',(),{'exists':lambda self:True})()
        with patch.object(engine,'YCRUNCHER',executable):
            plan=engine.computation_plan(2000000,constant='e')
            self.assertEqual(plan['outputFormat'],'ycd');self.assertFalse(plan['reducedFormula'])
    def test_cache_identity_worker_and_wrong_constant_rejection(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for name in ('pi','e','sqrt2','phi'):
                (folder/'request.json').write_text(json.dumps({'constant':name}))
                engine.worker(1000,'exact',folder,request_name='request.json')
                path=resource_plan.dataset_path(folder,1000,constant=name)
                self.assertEqual(path.name,name+'-1000.txt')
                meta=json.loads(path.with_suffix('.json').read_text());self.assertEqual(meta['constant'],name)
                store=DigitStore(path)
                try:self.assertEqual(store[:50].decode(),constants.CONSTANTS[name]['prefix']);self.assertEqual(store.constant,name)
                finally:store.close()
            with self.assertRaises(ValueError):DigitStore(folder/'e-1000.txt',constant='pi')
            self.assertEqual(len(list(folder.glob('*-1000.txt'))),4)
    def test_packed_constants_and_source_comparison(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp)
            for name in ('e','sqrt2','sqrt3','sqrt5','phi'):
                raw=engine.compute_constant(1000,name).encode();spec=constants.CONSTANTS[name]
                header=f'#Compressed Digit File\nFileVersion:\t1.1.0\nBase:\t10\nFirstDigits:\t{spec["integer"]}.{spec["prefix"]}\nTotalDigits:\t1000\nBlocksize:\t1000\nBlockID:\t0\n\0'.encode()
                packed=folder/(name+'-1000.ycd');plain=folder/(name+'-1000.txt')
                packed.write_bytes(header+b''.join(struct.pack('<Q',int(raw[i:i+19].ljust(19,b'0'))) for i in range(0,len(raw),19)));plain.write_bytes(str(spec['integer']).encode()+b'.'+raw)
                self.assertTrue(equal_files(plain,packed))
                store=DigitStore(packed)
                try:
                    self.assertEqual(store[17:71],raw[17:71]);self.assertEqual(store.constant,name)
                    self.assertEqual(store.tile(20,0,0,1,10,1,1)[0],raw[:10])
                finally:store.close()
    def test_native_configs_keep_packed_output_and_use_correct_algorithms(self):
        with tempfile.TemporaryDirectory() as tmp:
            for name,spec in constants.CONSTANTS.items():
                folder=Path(tmp)
                plan=resource_plan.plan(1000000,folder,800*resource_plan.MIB,mode='disk',memory_mib=128,free=30*resource_plan.GIB,low_disk=True,constant=name)
                config=native_runner.configuration(folder,1000000,{'constant':name,'lowDisk':True},plan).read_text()
                self.assertIn('Framework : "ycd"',config);self.assertIn('OutputVerify : true',config)
                if name=='e':self.assertIn('Algorithm : "exp(1)"',config)
                if name.startswith('sqrt'):self.assertIn('Argument : '+str(spec['radicand']),config)
                if name!='pi':self.assertNotIn('chudnovsky',config.lower());self.assertFalse(plan['reducedFormula'])
    def test_switching_constants_never_evicts_a_dataset_larger_than_cache_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);large=folder/'pi-1000.txt';large.write_bytes(b'x'*1000)
            large.with_suffix('.json').write_text(json.dumps({'cacheManaged':True}))
            small=folder/'e-50.txt';small.write_bytes(b'x'*50);small.with_suffix('.json').write_text(json.dumps({'cacheManaged':True}))
            resource_plan.prune_cache(folder,keep=(small.name,),quota=100)
            self.assertTrue(large.exists());self.assertTrue(small.exists())
    def test_reference_spot_check_is_not_required_when_unavailable_but_native_checks_are(self):
        log='Verifying Base Conversion:\nVerifying Decimal Output:\nTotal Computation Time: 1\nSpot Check: Unavailable - Digit file not found.'
        self.assertTrue(native_runner.native_verified(log,'sqrt3',0))
        self.assertFalse(native_runner.native_verified(log,'sqrt3',1))
        self.assertFalse(native_runner.native_verified(log.replace('Verifying Decimal Output:',''),'sqrt3',0))
        self.assertFalse(native_runner.native_verified(log+'\nSpot Check: Failed','sqrt3',0))
        self.assertFalse(native_runner.native_verified(log,'pi',0))

class ConstantApiTests(unittest.TestCase):
    def test_loaded_constant_status_export_and_cache_isolation(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);path=folder/'e-1000.txt';path.write_text(engine.compute_constant(1000,'e'))
            path.with_suffix('.json').write_text(json.dumps({'constant':'e','method':'exact'}))
            original=server.DIGITS;state=dict(server.STATE)
            try:
                with patch.object(server,'DATA',folder):
                    server.load_file(path)
                    httpd=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=httpd.serve_forever,daemon=True);thread.start()
                    try:
                        client=http.client.HTTPConnection('127.0.0.1',httpd.server_port,timeout=5)
                        client.request('GET','/api/status');response=client.getresponse();status=json.loads(response.read());self.assertEqual(status['constant'],'e');self.assertEqual(status['integerPart'],2)
                        client.request('GET','/api/export');response=client.getresponse();self.assertTrue(response.read().startswith(b'2.718281828'))
                        client.request('GET','/api/plan?count=1000&constant=e');response=client.getresponse();self.assertEqual(json.loads(response.read())['mode'],'cache')
                        client.request('GET','/api/plan?count=1000&constant=pi');response=client.getresponse();self.assertNotEqual(json.loads(response.read()).get('mode'),'cache');client.close()
                    finally:httpd.shutdown();httpd.server_close();thread.join()
            finally:
                if server.DIGITS is not original:server.DIGITS.close()
                server.DIGITS=original;server.STATE.clear();server.STATE.update(state)

if __name__=='__main__':unittest.main()
