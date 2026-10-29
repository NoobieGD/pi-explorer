import sys,os,json,time,tempfile,unittest,subprocess
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import server,native_runner,resource_plan,native_install

class NativeStartupTests(unittest.TestCase):
 def test_installed_distribution_can_use_another_extracted_folder(self):
  with tempfile.TemporaryDirectory() as tmp,patch.dict(os.environ,{},clear=True):
   root=Path(tmp);exe=root/'vendor/y-cruncher/new-release/y-cruncher.exe';exe.parent.mkdir(parents=True);exe.write_bytes(b'test')
   self.assertEqual(native_install.find_native(root),exe.resolve())
 def test_missing_native_reports_installation_instructions(self):
  with tempfile.TemporaryDirectory() as tmp:
   with self.assertRaisesRegex(FileNotFoundError,'COMPLETE official distribution'):native_install.require_native(Path(tmp)/'missing.exe')
 def test_large_worker_stderr_does_not_deadlock_monitor(self):
  real_popen=subprocess.Popen
  with tempfile.TemporaryDirectory() as tmp,patch.object(server,'DATA',Path(tmp)):
   def noisy(*args,**kwargs):
    return real_popen([sys.executable,'-c',"import sys;sys.stderr.write('x'*200000+'\\nBROKEN_NATIVE_TEST\\n');sys.exit(1)"],**kwargs)
   with patch.object(server.subprocess,'Popen',side_effect=noisy):
    started=time.monotonic();server.compute_job(1000,'ycruncher',True,{})
   self.assertLess(time.monotonic()-started,10)
   self.assertFalse(server.STATE['busy']);self.assertIn('BROKEN_NATIVE_TEST',server.STATE['error'])
   self.assertIn('BROKEN_NATIVE_TEST',(Path(tmp)/'last-computation-error.log').read_text())
 def test_silent_native_process_times_out_and_writes_a_result(self):
  with tempfile.TemporaryDirectory() as tmp:
   root=Path(tmp);work=root/'data/native-output/run-1000-1234abcd';work.mkdir(parents=True)
   plan=resource_plan.plan(1000,root,1024**3,mode='ram',free=30*1024**3)
   (work/'request.json').write_text(json.dumps({'digits':1000,'ownerPid':os.getpid(),'plan':plan,'options':{'liveTelemetry':False}}))
   with patch.object(native_runner,'ROOT',root),patch.object(native_runner,'STARTUP_TIMEOUT',.2),patch.object(native_runner,'command_for',return_value=[sys.executable,'-c','import time;time.sleep(60)']):
    self.assertEqual(native_runner.run(work/'request.json'),1)
   result=json.loads((work/'runner-result.json').read_text())
   self.assertEqual(result['status'],'timed_out');self.assertIn('startup output',result['error'])

 def test_process_launch_failure_is_reported_without_a_secondary_exception(self):
  with tempfile.TemporaryDirectory() as tmp,patch.object(server,'DATA',Path(tmp)),patch.object(server.subprocess,'Popen',side_effect=OSError('worker launch failed')):
   server.compute_job(1000,'ycruncher',True,{})
   self.assertFalse(server.STATE['busy']);self.assertIn('worker launch failed',server.STATE['error'])
