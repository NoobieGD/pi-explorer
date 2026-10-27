import unittest,tempfile,json,os
from pathlib import Path
from unittest.mock import patch
import resource_plan as r
import native_runner as runner
import engine

class ResourceTests(unittest.TestCase):
    def test_low_ram_switches_to_bounded_disk_blocks(self):
        p=r.plan(1_000_000_000,'.',800*r.MIB,free=30*r.GIB)
        self.assertEqual(p['mode'],'disk');self.assertLess(p['ramBudgetBytes'],500*r.MIB)
        self.assertEqual(p['scratchLimitBytes'],10_000_000_000+128*r.MIB)
        self.assertEqual(p['outputBytes'],1_000_000_002)
    def test_plenty_of_ram_retains_the_fast_path(self):
        p=r.plan(1_000_000_000,'.',8*r.GIB,free=30*r.GIB)
        self.assertEqual(p['mode'],'ram');self.assertEqual(p['scratchLimitBytes'],0)
    def test_forced_disk_and_manual_memory_budget(self):
        p=r.plan(1_000_000,'.',4*r.GIB,mode='disk',memory_mib=128,free=30*r.GIB)
        self.assertEqual(p['mode'],'disk');self.assertEqual(p['ramBudgetBytes'],128*r.MIB)
    def test_disk_and_ram_headroom_are_enforced(self):
        with self.assertRaises(OSError):r.plan(1_000_000_000,'.',800*r.MIB,free=3*r.GIB)
        with self.assertRaises(MemoryError):r.plan(1_000_000_000,'.',350*r.MIB,free=30*r.GIB)
        with self.assertRaises(MemoryError):r.plan(1_000_000_000,'.',800*r.MIB,mode='ram',free=30*r.GIB)
    def test_scratch_cleanup_never_reaches_other_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'native-output';work=root/'run-1000-1234abcd';scratch=work/'swap';scratch.mkdir(parents=True)
            (scratch/'block').write_bytes(b'x'*20);output=work/'Pi - Dec.txt';output.write_bytes(b'3.1415')
            cache=Path(directory)/'pi-1000.txt';cache.write_bytes(b'keep')
            with self.assertRaises(ValueError):r.cleanup(Path(directory),root,True)
            r.cleanup(work,root,True);self.assertFalse(scratch.exists());self.assertFalse(output.exists());self.assertEqual(cache.read_bytes(),b'keep')
    def test_cache_quota_keeps_active_and_imported_files(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            for i in range(1,5):
                path=root/f'pi-{i}.txt';path.write_bytes(b'x'*20);path.with_suffix('.json').write_text(json.dumps({'cacheManaged':i!=1}))
                os.utime(path,(i,i))
            size=r.prune_cache(root,keep=('pi-2.txt','pi-4.txt'),quota=40)
            self.assertEqual(size,40);self.assertTrue((root/'pi-1.txt').exists());self.assertTrue((root/'pi-2.txt').exists());self.assertFalse((root/'pi-3.txt').exists());self.assertTrue((root/'pi-4.txt').exists())
    def test_native_disk_command_caps_ram_and_keeps_verification(self):
        p=r.plan(1_000_000_000,'.',800*r.MIB,free=30*r.GIB)
        cmd=runner.command_for(Path('native.exe'),Path('work'),1_000_000_000,{'ioProfile':'legacy'},p)
        self.assertIn('-mode:swap',cmd);self.assertIn('-M:'+str(p['ramBudgetBytes']),cmd);self.assertIn('-verify:1',cmd)
        self.assertEqual(cmd[-2:],['-swap:raid0',str(Path('work/swap'))])
    def test_cancelled_helper_cleans_blocks_without_publishing(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);work=root/'data/native-output/run-1000000-1234abcd';work.mkdir(parents=True)
            plan=r.plan(1_000_000,root,800*r.MIB,mode='disk',memory_mib=128,free=30*r.GIB)
            (work/'request.json').write_text(json.dumps({'digits':1_000_000,'ownerPid':os.getpid(),'plan':plan}))
            (work/'cancel').touch();(work/'Pi - Dec.txt').write_text('3.1415')
            class Process:
                dead=False
                pid=os.getpid()
                import io
                stdout=io.BytesIO()
                def poll(self):return 1 if self.dead else None
                def wait(self,timeout):return 1
            proc=Process()
            with patch.object(runner,'ROOT',root),patch.object(runner,'command_for',return_value=['native.exe']),patch.object(runner.subprocess,'Popen',return_value=proc),patch.object(runner,'stop_native',side_effect=lambda p:setattr(p,'dead',True)):
                self.assertEqual(runner.run(work/'request.json'),1)
            self.assertEqual(json.loads((work/'runner-result.json').read_text())['status'],'cancelled')
            self.assertFalse((work/'swap').exists());self.assertFalse((work/'Pi - Dec.txt').exists())
    def test_scratch_monitor_tolerates_native_file_rotation(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'block';path.write_bytes(b'123')
            real_stat=Path.stat
            def raced(p,*a,**kw):
                if p==path:raise FileNotFoundError('Native worker replaced its scratch block')
                return real_stat(p,*a,**kw)
            with patch.object(Path,'stat',raced):self.assertEqual(r.job_bytes(root),0)
    def test_ssd_configuration_preserves_checks_and_bounds_buffers(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);plan=r.plan(1_000_000,'.',800*r.MIB,mode='disk',memory_mib=128,free=30*r.GIB)
            cfg=runner.configuration(root,1_000_000,{'cores':'0,1','tasks':2},plan).read_text(encoding='utf-8')
            self.assertIn('BufferPerWorker : 1048576',cfg);self.assertIn('Workers : 2',cfg);self.assertIn('LaneMultiplier : 2',cfg)
            self.assertIn('OutputVerify : true',cfg);self.assertIn('Checksums : true',cfg);self.assertIn('Enabled : false',cfg)
            self.assertIn('LogicalCores : ["0" "1"]',cfg);self.assertIn('EnableHexDigits : false',cfg);self.assertNotIn('\ufeff',cfg)
    def test_cpu_tuning_does_not_escape_its_tested_size_or_machine(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);identity={'processor':engine.platform.processor(),'logicalCores':os.cpu_count()}
            profile={'disk':{'ioProfile':'ssd','cores':'0-3','tasks':4},'ram':{},'tunedThroughDigits':25_000_000,'cpuSignature':identity}
            (root/'request.json').write_text(json.dumps({'storageMode':'disk'}))
            for count,matches,expected in ((25_000_000,True,True),(1_000_000_000,True,False),(25_000_000,False,False)):
                profile['cpuSignature']=identity if matches else {'processor':'different','logicalCores':1}
                (root/'performance-profile.json').write_text(json.dumps(profile))
                with patch.object(engine,'available_memory',return_value=r.GIB),patch.object(engine,'compute_ycruncher_file',side_effect=RuntimeError('before native calculation')) as native:
                    with self.assertRaisesRegex(RuntimeError,'before native calculation'):engine.worker(count,'ycruncher',root,request_name='request.json')
                options=native.call_args.args[3];self.assertEqual('cores' in options,expected);self.assertEqual(options['ioProfile'],'ssd')

if __name__=='__main__':unittest.main()
