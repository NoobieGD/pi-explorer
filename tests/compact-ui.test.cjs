const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),vm=require('node:vm'),path=require('node:path');
const source=fs.readFileSync(path.join(__dirname,'../app/app.js'),'utf8');
test('target check is GET-only and labels the absence of a storage proof',async()=>{
 const code=source.slice(source.indexOf('async function checkCompactTarget()'),source.indexOf('function geometry()'));
 const nodes=new Map(),calls=[];const context=vm.createContext({$:id=>{if(!nodes.has(id))nodes.set(id,{});return nodes.get(id)},api:async(path,body)=>{calls.push([path,body]);return{verifiedUnderBudget:false,textOutputBytes:200000000002,temporaryBudgetAfterTextBytes:25485783038}}});
 vm.runInContext(code,context);await vm.runInContext('checkCompactTarget()',context);
 assert.equal(calls.length,1);assert.equal(calls[0][0],'compact-check?count=200000000000');assert.equal(calls[0][1],undefined);
 assert.match(nodes.get('compactCheckResult').textContent,/^NOT VERIFIED/);assert.match(nodes.get('compactCheckResult').textContent,/186\.26 GiB/);assert.equal(nodes.get('compactCheckBtn').disabled,false);
});
