/* Standalone HTML transport for the shared Pi Explorer interface. */
'use strict';
(()=>{
 const SEED=window.PI_BUNDLED_DIGITS;
 const workerSource=document.getElementById('pi-worker-source').textContent;
 const workerUrl=URL.createObjectURL(new Blob([workerSource],{type:'text/javascript'}));
 let sequence=0,backend,computer,ready,computePromise=null;
 const pending=new Map(),jobs=new Map();
 const status={count:SEED.length,busy:false,progress:1,message:'Verified bundled digits loaded',method:'bundled',seconds:0,token:'browser-local',maxDigits:null,datasetId:1};
 const dataCache=new Map([[SEED.length,SEED]]);
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
 async function storeCache(digits,method){try{const db=await openCache();await new Promise((resolve,reject)=>{const tx=db.transaction('digits','readwrite');tx.objectStore('digits').put({digits,method},'latest');tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>{db.close();reject(tx.error);};});}catch{}}
 async function useDigits(digits,method,seconds=0){await rpc(backend,'setDigits',{digits});Object.assign(status,{count:digits.length,method,seconds,busy:false,progress:1,error:null,cancelled:false,message:'Ready to explore',datasetId:status.datasetId+1});dataCache.set(digits.length,digits);if(dataCache.size>4)dataCache.delete([...dataCache.keys()].find(k=>k!==SEED.length));void storeCache(digits,method);}
 backend=makeWorker();attach(backend);
 ready=(async()=>{const saved=await readCache();const valid=saved&&typeof saved.digits==='string'&&/^\d+$/.test(saved.digits)&&saved.digits.startsWith(SEED.slice(0,Math.min(50,saved.digits.length)));
  const digits=valid?saved.digits:SEED;await rpc(backend,'init',{digits});Object.assign(status,{count:digits.length,method:valid?saved.method:'bundled',message:valid?'Restored browser cache':'Verified bundled digits loaded'});if(valid)dataCache.set(digits.length,digits);
 })();
 async function startCompute(count,force=false){
  if(status.busy)throw Error('A computation is already running.');if(!Number.isSafeInteger(count)||count<1)throw Error('Enter a positive count this browser can represent exactly. Use the desktop native engine for larger counts.');
  Object.assign(status,{busy:true,progress:0,error:null,cancelled:false,message:'Starting browser precision worker',target:count,startedAt:performance.now()});
  if(dataCache.has(count)&&!force){await useDigits(dataCache.get(count),count===SEED.length?'bundled':'browser');return;}
  computer=makeWorker();attach(computer);const instance=computer;
  computePromise=rpc(instance,'compute',{count}).then(async result=>{if(computer!==instance)return;const known=dataCache.get(count)||SEED;if(count<=known.length&&result.digits!==known.slice(0,count))throw Error('Computed digits disagree with the verified bundle.');await useDigits(result.digits,'browser',result.seconds);}).catch(error=>{if(computer===instance)Object.assign(status,{busy:false,error:error.message,message:'Computation failed'});}).finally(()=>{instance.terminate();if(computer===instance)computer=null;});
 }
 window.PiLocalApi={maxComputeDigits:null,ready,
  async request(path,body){
   await ready;const [route,query='']=path.split('?');const params=Object.fromEntries(new URLSearchParams(query));
   if(route==='status')return{...status,elapsed:status.busy?(performance.now()-status.startedAt)/1000:undefined};
   if(route==='digits')return rpc(backend,'digits',params);
   if(route==='tile')return rpc(backend,'tile',params);
   if(route==='stats')return rpc(backend,'stats');
   if(route==='export')return rpc(backend,'export');
   if(route==='compute'){await startCompute(+body.count,!!body.force);return{ok:true};}
   if(route==='cancel'){
    if(computer){const target=computer;computer=null;target.terminate();for(const [id,p] of pending)if(p.worker===target){pending.delete(id);p.reject(Error('Computation cancelled'));}}
    Object.assign(status,{busy:false,cancelled:true,progress:0,error:null,message:'Computation cancelled'});return{ok:true};
   }
   if(route==='search'){const result=await rpc(backend,'search',body);if(!jobs.has(result.id))jobs.set(result.id,{id:result.id,status:'running',message:'Preparing search',progress:0});return result;}
   if(route.startsWith('job/')){const job=jobs.get(route.slice(4));if(!job)throw Error('Search not found');return{...job};}
   if(route==='search/cancel')return rpc(backend,'cancelSearch',body);
   if(route==='import'){
    if(status.busy)throw Error('Wait for computation before importing.');let digits=String(body.digits||'').trim();if(digits.startsWith('3.'))digits=digits.slice(2);digits=digits.replace(/\s/g,'');
    if(digits.length<50||!/^\d+$/.test(digits)||!digits.startsWith(SEED.slice(0,50)))throw Error('Import decimal digits of pi. The first 50 must match.');
    await useDigits(digits,'imported (prefix checked)');return{ok:true,count:digits.length};
   }
   if(route==='restore'){if(status.busy)throw Error('Cancel computation first.');await useDigits(SEED,'bundled');return{ok:true};}
   if(route==='shutdown')return{ok:true};
   throw Error('Unknown browser command: '+route);
  }
 };
})();
