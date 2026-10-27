"""Compact app integration; all calculations here are at most 100K digits."""
import sys,json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
import engine,server

class CompactAppTests(unittest.TestCase):
    def test_dispatch_progress_and_independent_verification(self):
        events=[];value=engine.compute_pi(10000,'compact',lambda p,m:events.append((p,m)))
        self.assertEqual(value,engine.compute_pi(10000,'mpfr'))
        self.assertTrue(any('MPFR verification' in label for _,label in events))
        self.assertTrue(any('common factors' in label or 'Splitting' in label for _,label in events))
        def cancelled(*args):raise InterruptedError('Cancelled')
        with self.assertRaises(InterruptedError):engine.compute_pi(10000,'compact',cancelled)
    def test_real_worker_saves_verified_metadata_and_reuses_identical_file(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);engine.worker(100000,'compact',folder)
            digits=folder/'pi-100000.txt';self.assertEqual(digits.read_text(),engine.compute_pi(100000,'mpfr'))
            info=json.loads(digits.with_suffix('.json').read_text())
            self.assertEqual(info['method'],'compact')
            self.assertEqual(info['compact']['verification'],'Full independent MPFR comparison')
            stamp=digits.stat().st_mtime_ns
            engine.worker(100000,'compact',folder)
            self.assertEqual(digits.stat().st_mtime_ns,stamp)
    def test_large_check_and_compute_rejection_start_no_worker(self):
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{http.server_port}/api/'
        try:
            with patch.object(server,'compute_job') as worker,patch.object(engine,'available_memory',return_value=800*1024**2):
                check=json.load(urllib.request.urlopen(base+'compact-check?count=200000000000'))
                self.assertTrue(check['nonComputingCheck']);self.assertFalse(check['verifiedUnderBudget'])
                self.assertIsNone(check['peakStorageUpperBoundBytes'])
                self.assertEqual(check['textOutputBytes'],200000000002)
                plan=json.load(urllib.request.urlopen(base+'plan?method=compact&count=200000000000&force=true'))
                self.assertFalse(plan['launchable']);self.assertTrue(plan['experimental'])
                self.assertGreater(plan['compactMaxDigitsForRam'],100000)
                self.assertIn('Use Auto',plan['message'])
                req=urllib.request.Request(base+'compute',json.dumps({'method':'compact','count':'200000000000','force':True}).encode(),{'Content-Type':'application/json','X-Pi-Token':server.TOKEN})
                with self.assertRaises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
                self.assertEqual(error.exception.code,422);worker.assert_not_called()
        finally:http.shutdown();http.server_close();thread.join()
    def test_disk_selection_never_silently_switches_compact_to_native(self):
        with tempfile.TemporaryDirectory() as directory:
            folder=Path(directory);(folder/'request.json').write_text(json.dumps({'storageMode':'disk'}))
            with patch.object(engine,'compute_ycruncher_file') as native:
                with self.assertRaisesRegex(ValueError,'RAM-only'):engine.worker(100000,'compact',folder,request_name='request.json')
                native.assert_not_called()

if __name__=='__main__':unittest.main()
