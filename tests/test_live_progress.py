import unittest,time,os,json,tempfile,http.client,threading
from pathlib import Path
from unittest.mock import patch
from live_progress import NativeProgress,ProcessSampler
import server

class ParserTests(unittest.TestCase):
    def test_native_carriage_return_updates_and_chunk_splits(self):
        p=NativeProgress(1000);p.feed(b'Series CommonP2B3...\r\n\rSumming: 1');self.assertIsNone(p.snapshot()['phaseProgress'])
        p.feed(b'2% (4) A (1,000)\r');s=p.snapshot();self.assertEqual(s['phaseProgress'],.12);self.assertEqual(s['phase'],'series');self.assertEqual(s['phaseStep'],2)
        p.feed(b'\x1b[2K\rSumming: 47%\r');self.assertEqual(p.snapshot()['phaseProgress'],.47)
    def test_new_phase_resets_fraction_and_output_hash_is_real_progress(self):
        p=NativeProgress(1000);p.feed(b'Series CommonP2B3...\rSumming: 80%\rLarge Division...\n')
        s=p.snapshot();self.assertEqual(s['phase'],'divide');self.assertIsNone(s['phaseProgress'])
        p.feed(b'Verifying Decimal Output:\nVerifying... 500 digits hashed\r');self.assertEqual(p.snapshot()['phaseProgress'],.5)
    def test_completion_requires_complete_matching_spot_check_line(self):
        p=NativeProgress(1000);p.feed(b'Total Computation Time: 1.0\nSpot Check: Good through 1,000')
        self.assertFalse(p.verified);p.feed(b',000\n');self.assertFalse(p.verified)
        p.feed(b'Spot Check: Good through 1,000\n');self.assertTrue(p.verified);self.assertTrue(p.total_time)
    def test_stream_tail_and_unterminated_status_are_bounded(self):
        p=NativeProgress(1000)
        for _ in range(60):p.feed(b'x'*8192)
        self.assertLessEqual(len(p.transcript_tail()),128*1024);self.assertLessEqual(p.tail_bytes,128*1024);self.assertLessEqual(len(p.pending),4096)
    @unittest.skipUnless(os.name=='nt','Windows process metrics')
    def test_process_sampler_reads_cpu_memory_and_io_without_math_imports(self):
        sampler=ProcessSampler(os.getpid())
        try:
            sampler.sample();until=time.perf_counter()+.04
            while time.perf_counter()<until:pass
            sample=sampler.sample();self.assertGreater(sample['residentBytes'],0);self.assertGreater(sample['cpuPercent'],0);self.assertGreaterEqual(sample['readBytesPerSecond'],0)
        finally:sampler.close()

class StatusTests(unittest.TestCase):
    def test_api_reads_live_snapshot_directly_without_worker_progress_rewrites(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'native-output/run-1000-1234abcd';work.mkdir(parents=True)
            service=server.ThreadingHTTPServer(('127.0.0.1',0),server.Handler);thread=threading.Thread(target=service.serve_forever,daemon=True);thread.start()
            try:
                with patch.object(server,'DATA',root),patch.object(server,'STATE',{'busy':True,'nativeJob':work.name,'count':50,'startedAt':time.perf_counter()}):
                    for percent in (.2,.7):
                        (work/'telemetry.json').write_text(json.dumps({'updatedAt':time.time(),'overallEstimate':.05,'phaseLabel':'Series summation','phaseProgress':percent}))
                        client=http.client.HTTPConnection('127.0.0.1',service.server_port);client.request('GET','/api/status');response=client.getresponse();result=json.loads(response.read());client.close()
                        self.assertEqual(result['telemetry']['phaseProgress'],percent);self.assertEqual(result['message'],'Series summation');self.assertEqual(result['count'],50);self.assertLess(result['telemetry']['ageSeconds'],1)
            finally:service.shutdown();service.server_close();thread.join()

if __name__=='__main__':unittest.main()
