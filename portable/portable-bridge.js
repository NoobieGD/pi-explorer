/* Standalone HTML transport for the shared Pi Explorer interface. */
'use strict';
(()=>{
 const SEED=window.PI_BUNDLED_DIGITS;
 const NUMBERS={"pi": {"label": "Pi", "symbol": "π", "integer": 3, "prefix": "14159265358979323846264338327950288419716939937510", "native": "pi", "algorithm": "chudnovsky"}, "e": {"label": "Euler's number", "symbol": "e", "integer": 2, "prefix": "71828182845904523536028747135266249775724709369995", "native": "e", "algorithm": "exp(1)"}, "sqrt2": {"label": "Square root of 2", "symbol": "√2", "integer": 1, "prefix": "41421356237309504880168872420969807856967187537694", "native": "sqrt:2", "algorithm": "newton", "radicand": 2}, "sqrt3": {"label": "Square root of 3", "symbol": "√3", "integer": 1, "prefix": "73205080756887729352744634150587236694280525381038", "native": "sqrt:3", "algorithm": "newton", "radicand": 3}, "sqrt5": {"label": "Square root of 5", "symbol": "√5", "integer": 2, "prefix": "23606797749978969640917366873127623544061835961152", "native": "sqrt:5", "algorithm": "newton", "radicand": 5}, "phi": {"label": "Golden ratio", "symbol": "φ", "integer": 1, "prefix": "61803398874989484820458683436563811772030917980576", "native": "phi", "algorithm": "newton"}};
 const cacheKey=(constant,count)=>constant+':'+count;
 const workerSource=document.getElementById('pi-worker-source').textContent;
 const workerUrl=URL.createObjectURL(new Blob([workerSource],{type:'text/javascript'}));
 let sequence=0,backend,computer,ready,computePromise=null;
 const pending=new Map(),jobs=new Map();
 const status={constant:'pi',integerPart:3,constants:Object.entries(NUMBERS).map(([id,spec])=>({id,...spec})),count:SEED.length,busy:false,progress:1,message:'Verified bundled digits loaded',method:'bundled',seconds:0,token:'browser-local',maxDigits:null,datasetId:1};
 const dataCache=new Map([[cacheKey('pi',SEED.length),SEED]]);
 function makeWorker(){return new Worker(workerUrl);}
 function rpc(worker,cmd,args={}){return new Promise((resolve,reject)=>{const id=++sequence;pending.set(id,{resolve,reject,worker});worker.postMessage({id,cmd,args});});}
 function attach(worker){
  worker.onmessage=({data})=>{
   if(data.type==='job'){jobs.set(data.job.id,data.job);return;}
   if(data.type==='computeProgress'){Object.assign(status,{progress:data.progress,message:data.message});return;}
   const request=pending.get(data.id);if(!request)return;pending.delete(data.id);if(data.error)request.reject(Error(data.error));else request.resolve(data.result);
  };
  worker.onerror=event=>{const error=Error(event.message||'The browser worker stopped. Reopen this HTML file.');for(const [id,request] of pending)if(request.worker===worker){pending.delete(id);request.reject(error);}if(worker===computer)Object.assign(status,{busy:false,error:error.message,message:'Computation failed'});};
 }
 function openCache(){return new Promise((resolve,reject)=>{if(!window.indexedDB){reject(Error('Browser cache unavailable'));return;}const req=indexedDB.open('pi-explorer-standalone-v1',1);req.onupgradeneeded=()=>{if(!req.result.objectStoreNames.contains('digits'))req.result.createObjectStore('digits');};req.onsuccess=()=>resolve(req.result);req.onerror=()=>reject(req.error);req.onblocked=()=>reject(Error('Browser cache blocked'));});}
 async function readCache(){try{const db=await openCache();return await new Promise(resolve=>{const tx=db.transaction('digits','readonly'),r=tx.objectStore('digits').get('latest');r.onsuccess=()=>resolve(r.result);r.onerror=()=>resolve(null);tx.oncomplete=()=>db.close();});}catch{return null;}}
 async function storeCache(digits,method,constant='pi'){try{const db=await openCache();await new Promise((resolve,reject)=>{const tx=db.transaction('digits','readwrite');tx.objectStore('digits').put({digits,method,constant},'latest');tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>{db.close();reject(tx.error);};});}catch{}}
 async function useDigits(digits,method,seconds=0,constant='pi'){
  if(!NUMBERS[constant]||!digits.startsWith(NUMBERS[constant].prefix.slice(0,Math.min(50,digits.length))))throw Error('Constant prefix mismatch');
  await rpc(backend,'setDigits',{digits,constant});
  Object.assign(status,{constant,integerPart:NUMBERS[constant].integer,count:digits.length,method,seconds,busy:false,progress:1,error:null,cancelled:false,message:'Ready to explore',datasetId:status.datasetId+1});
  const key=cacheKey(constant,digits.length);dataCache.set(key,digits);
  while(dataCache.size>4){const oldest=[...dataCache.keys()].find(k=>k!==cacheKey('pi',SEED.length)&&k!==key);if(!oldest)break;dataCache.delete(oldest);}
  void storeCache(digits,method,constant);
 }
 backend=makeWorker();attach(backend);
 ready=(async()=>{
  const saved=await readCache(),constant=saved?.constant||'pi',spec=NUMBERS[constant];
  const valid=saved&&spec&&typeof saved.digits==='string'&&/^\d+$/.test(saved.digits)&&saved.digits.startsWith(spec.prefix.slice(0,Math.min(50,saved.digits.length)));
  const selected=valid?constant:'pi',digits=valid?saved.digits:SEED;
  await rpc(backend,'init',{digits,constant:selected});
  Object.assign(status,{constant:selected,integerPart:NUMBERS[selected].integer,count:digits.length,method:valid?saved.method:'bundled',message:valid?'Restored browser cache':'Verified bundled digits loaded'});
  if(valid)dataCache.set(cacheKey(selected,digits.length),digits);
 })();
 async function startCompute(count,force=false,constant='pi'){
  if(!NUMBERS[constant])throw Error('Unknown constant');
  if(status.busy)throw Error('A computation is already running.');
  if(!Number.isSafeInteger(count)||count<1)throw Error('Enter a positive exact count; use the desktop engine for larger runs.');
  Object.assign(status,{busy:true,targetConstant:constant,progress:0,error:null,cancelled:false,message:'Starting browser precision worker',target:count,startedAt:performance.now()});
  const key=cacheKey(constant,count);
  if(dataCache.has(key)&&!force){await useDigits(dataCache.get(key),constant==='pi'&&count===SEED.length?'bundled':'browser',0,constant);return;}
  computer=makeWorker();attach(computer);const instance=computer;
  computePromise=rpc(instance,'compute',{count,constant}).then(async result=>{
   if(computer!==instance)return;
   const known=dataCache.get(key)||(constant==='pi'?SEED:null);
   if(known&&count<=known.length&&result.digits!==known.slice(0,count))throw Error('Computed digits disagree with cached digits of this constant.');
   await useDigits(result.digits,'browser',result.seconds,constant);
  }).catch(error=>{if(computer===instance)Object.assign(status,{busy:false,error:error.message,message:'Computation failed'});}).finally(()=>{instance.terminate();if(computer===instance)computer=null;});
 }
 window.PiLocalApi={maxComputeDigits:null,ready,
  async request(path,body){
   await ready;const [route,query='']=path.split('?');const params=Object.fromEntries(new URLSearchParams(query));
   if(route==='status')return{...status,elapsed:status.busy?(performance.now()-status.startedAt)/1000:undefined};
   if(route==='digits')return rpc(backend,'digits',params);
   if(route==='tile')return rpc(backend,'tile',params);
   if(route==='stats')return rpc(backend,'stats');
   if(route==='export')return rpc(backend,'export');
   if(route==='compute'){await startCompute(+body.count,!!body.force,body.constant||'pi');return{ok:true};}
   if(route==='cancel'){
    if(computer){const target=computer;computer=null;target.terminate();for(const [id,p] of pending)if(p.worker===target){pending.delete(id);p.reject(Error('Computation cancelled'));}}
    Object.assign(status,{busy:false,cancelled:true,progress:0,error:null,message:'Computation cancelled'});return{ok:true};
   }
   if(route==='search'){const result=await rpc(backend,'search',body);if(!jobs.has(result.id))jobs.set(result.id,{id:result.id,status:'running',message:'Preparing search',progress:0});return result;}
   if(route.startsWith('job/')){const job=jobs.get(route.slice(4));if(!job)throw Error('Search not found');return{...job};}
   if(route==='search/cancel')return rpc(backend,'cancelSearch',body);
   if(route==='import'){
    if(status.busy)throw Error('Wait for computation before importing.');const constant=body.constant||status.constant||'pi',spec=NUMBERS[constant];if(!spec)throw Error('Unknown constant');let digits=String(body.digits||'').trim();if(digits.startsWith(spec.integer+'.'))digits=digits.slice(2);digits=digits.replace(/\s/g,'');
    if(digits.length<50||!/^\d+$/.test(digits)||!digits.startsWith(spec.prefix))throw Error('Import '+spec.label+' digits. The first 50 must match.');
    await useDigits(digits,'imported (prefix checked)',0,constant);return{ok:true,count:digits.length};
   }
   if(route==='restore'){if(status.busy)throw Error('Cancel computation first.');await useDigits(SEED,'bundled');return{ok:true};}
   if(route==='shutdown')return{ok:true};
   throw Error('Unknown browser command: '+route);
  }
 };
})();
