const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const root=path.resolve(__dirname,'..'),workerSource=fs.readFileSync(root+'/portable/portable-engine.js','utf8'),bridge=fs.readFileSync(root+'/portable/portable-bridge.js','utf8'),E=require('../portable/portable-engine.js');
function setup(){
 class Worker{
  constructor(){const worker=this,self={postMessage(data){queueMicrotask(()=>{if(!worker.closed)worker.onmessage?.({data});});}};this.context={self,console,performance,TextDecoder,TextEncoder,Uint8Array,Uint32Array,BigInt,Map,Set,Math,setTimeout,clearTimeout};vm.createContext(this.context);vm.runInContext(workerSource,this.context);}
  postMessage(data){if(!this.closed)void this.context.self.onmessage({data});}
  terminate(){this.closed=true;}
 }
 const window={PI_BUNDLED_DIGITS:E.computePi(1000)},context={window,document:{getElementById(){return{textContent:workerSource};}},Worker,URL,URLSearchParams,Blob,performance,setTimeout,clearTimeout,console};vm.createContext(context);vm.runInContext(bridge,context);return window.PiLocalApi;
}
test('standalone transport isolates same-length constant caches and integer parts',async()=>{
 const api=setup();await api.ready;
 for(const constant of ['e','sqrt2','phi','pi','e']){
  await api.request('compute',{count:1000,constant});
  let status;for(let n=0;n<100;n++){status=await api.request('status');if(!status.busy)break;await new Promise(resolve=>setTimeout(resolve,1));}
  assert.equal(status.error,null);assert.equal(status.constant,constant);
  assert.equal(await api.request('export'),E.NUMBER_INFO[constant].integer+'.'+E.computeConstant(1000,constant));
 }
 await assert.rejects(()=>api.request('import',{constant:'e',digits:'3.'+E.computePi(1000)}),/first 50/);
 await api.request('import',{constant:'sqrt2',digits:'1.'+E.computeConstant(1000,'sqrt2')});
 assert.equal((await api.request('status')).constant,'sqrt2');
 await api.request('restore',{});assert.equal((await api.request('status')).constant,'pi');
});
