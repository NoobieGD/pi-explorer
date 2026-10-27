"""Large-count validation only: these tests never calculate large pi datasets."""
import json,tempfile,threading,unittest,urllib.request,urllib.error
from pathlib import Path
from unittest.mock import patch
import resource_plan as resources
import native_runner,engine,server

class UncappedTests(unittest.TestCase):
    def test_large_disk_plan_and_exact_native_configuration(self):
        for count in (200_000_000_000,10**12,9_007_199_254_740_993):
            plan=resources.plan(str(count),'.',800*resources.MIB,free=count*12+resources.GIB)
            self.assertEqual(plan['digits'],count)
            self.assertEqual(plan['outputBytes'],count+2)
            self.assertEqual(plan['scratchLimitBytes'],count*10+128*resources.MIB)
            with tempfile.TemporaryDirectory() as directory:
                cfg=native_runner.configuration(Path(directory),count,{},plan).read_text()
                self.assertIn(f'DecimalDigits : {count}',cfg)
        self.assertIsNone(engine.MAX_DIGITS)
    def test_limits_follow_resources_not_digit_ceiling(self):
        with self.assertRaisesRegex(OSError,'Not enough free disk space'):
            resources.plan(200_000_000_000,'.',800*resources.MIB,free=100*resources.GIB)
        with self.assertRaises(MemoryError):
            resources.plan(200_000_000_000,'.',800*resources.MIB,method='mpfr',free=10**15)
        for value in (0,-1,True,1.5,'1e12','-100'):
            with self.assertRaises(ValueError):resources.digit_count(value)
        self.assertEqual(resources.estimate_ram(10**400),(10**400*485+99)//100+40*resources.MIB)
    def test_api_preflight_and_rejected_large_post_do_not_start_worker(self):
        http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        base=f'http://127.0.0.1:{http.server_port}/api/'
        try:
            with patch.object(server.engine.resource_plan.shutil,'disk_usage',return_value=type('Disk',(),{'free':100*resources.GIB})()),patch.object(server.engine,'available_memory',return_value=800*resources.MIB),patch.object(server,'compute_job') as worker:
                status=json.load(urllib.request.urlopen(base+'status'));self.assertIsNone(status['maxDigits'])
                for path,body in [('plan?count=200000000000',None),('compute',{'count':'200000000000','method':'auto','force':True})]:
                    req=urllib.request.Request(base+path,None if body is None else json.dumps(body).encode(),{'Content-Type':'application/json','X-Pi-Token':server.TOKEN})
                    with self.assertRaises(urllib.error.HTTPError) as response:urllib.request.urlopen(req)
                    self.assertEqual(response.exception.code,422)
                    self.assertIn('Not enough free disk space',json.load(response.exception)['error'])
                worker.assert_not_called()
        finally:http.shutdown();http.server_close();thread.join()

if __name__=='__main__':unittest.main()
