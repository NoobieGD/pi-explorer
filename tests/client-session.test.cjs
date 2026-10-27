const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../app/app.js'),'utf8');
const functions=source.slice(source.indexOf('let sessionRefresh='),source.indexOf('function geometry()'));
const response=(status,data)=>({ok:status>=200&&status<300,status,json:async()=>data});
test('open client automatically recovers after server token changes',async()=>{
 const requests=[];const context=vm.createContext({state:{token:'old-token',shuttingDown:true},window:{},Date,Error,fetch:async(url,options)=>{
  requests.push([url,options]);if(url.includes('/api/status'))return response(200,{token:'new-token'});
  if(options.headers['X-Pi-Token']==='old-token')return response(403,{code:'SESSION_EXPIRED',error:'Session changed'});
  assert.equal(options.headers['X-Pi-Token'],'new-token');return response(200,{id:'search-ok'});
 }});vm.runInContext(functions,context);const result=await vm.runInContext("api('search',{mode:'digits',query:'12345'})",context);
 assert.equal(result.id,'search-ok');assert.equal(context.state.token,'new-token');assert.equal(context.state.shuttingDown,false);assert.equal(requests.length,3);
});
test('clicking immediately on startup fetches a session first',async()=>{
 const requests=[];const context=vm.createContext({state:{token:''},window:{},Date,Error,fetch:async(url,options)=>{requests.push(url);if(url.includes('/api/status'))return response(200,{token:'ready'});assert.equal(options.headers['X-Pi-Token'],'ready');return response(200,{ok:true});}});
 vm.runInContext(functions,context);await vm.runInContext("api('compute',{count:1000})",context);assert.ok(requests[0].includes('/api/status'));assert.equal(requests.length,2);
});
test('a rejected origin is not retried as a session expiry',async()=>{
 let requests=0;const context=vm.createContext({state:{token:'valid'},window:{},Date,Error,fetch:async()=>{requests++;return response(403,{error:'Local requests only'});}});vm.runInContext(functions,context);
 await assert.rejects(vm.runInContext("api('compute',{count:1000})",context),/Local requests only/);assert.equal(requests,1);
});
