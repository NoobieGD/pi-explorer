import unittest, tempfile, json, http.client, threading, os
from pathlib import Path
from unittest.mock import patch
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import storage
import server

class StorageTests(unittest.TestCase):
    def test_retry_windows_replace_lock(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'progress.json';p.write_text('old')
            replace=os.replace
            calls=[]
            def locked(a,b):
                calls.append(1)
                if len(calls)<3:raise PermissionError('Windows reader lock')
                return replace(a,b)
            with patch.object(storage.os,'replace',side_effect=locked):storage.atomic_write(p,'new',delay=0)
            self.assertEqual(p.read_text(),'new');self.assertEqual(len(calls),3)
    def test_progress_cannot_fail_computation(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/'progress.json';p.write_text('{"progress":0}')
            with patch.object(storage.os,'replace',side_effect=PermissionError('Locked')):
                self.assertFalse(storage.write_progress(p,.5,'Working'))
            self.assertEqual(json.loads(p.read_text()),{'progress':0})
            self.assertEqual(list(Path(folder).glob('*.tmp')),[])

class SessionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.http=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):cls.http.shutdown();cls.http.server_close();cls.thread.join()
    def test_expired_token_does_not_poison_next_request(self):
        client=http.client.HTTPConnection('127.0.0.1',self.http.server_port,timeout=3)
        client.request('POST','/api/search',json.dumps({'mode':'digits','query':'123'}),{'X-Pi-Token':'expired','Content-Type':'application/json'})
        result=client.getresponse();self.assertEqual(result.status,403);self.assertEqual(json.loads(result.read())['code'],'SESSION_EXPIRED');self.assertTrue(result.will_close)
        client.request('GET','/api/status');result=client.getresponse();self.assertEqual(result.status,200);token=json.loads(result.read())['token']
        client.request('POST','/api/search/cancel','{}',{'X-Pi-Token':token,'Content-Type':'application/json'})
        result=client.getresponse();self.assertEqual(result.status,200);self.assertTrue(json.loads(result.read())['ok']);client.close()
    def test_each_desktop_launch_forces_new_navigation(self):
        a=server.launch_url('http://127.0.0.1:31415');b=server.launch_url('http://127.0.0.1:31415')
        self.assertNotEqual(a,b);self.assertIn('?launch=',a)

if __name__=='__main__':unittest.main()
