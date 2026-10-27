const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const source=fs.readFileSync(path.join(__dirname,'../app/app.js'),'utf8');
const code=source.slice(source.indexOf('function engineChanged()'),source.indexOf('async function checkCompactTarget()'));
function setup(mode='auto'){
 const nodes={engineSelect:{value:'compact'},memoryMode:{value:mode},compactVerification:{hidden:true}},state={computing:false};let plans=0;
 const context=vm.createContext({state,$:id=>nodes[id],refreshPlan:()=>{plans++},toast:()=>{}});vm.runInContext(code,context);
 return{context,nodes,state,plans:()=>plans};
}
test('leaving compact restores Automatic instead of leaving RAM-only selected',()=>{
 const f=setup();vm.runInContext('engineChanged()',f.context);assert.equal(f.nodes.memoryMode.value,'ram');assert.equal(f.nodes.memoryMode.disabled,true);
 f.nodes.engineSelect.value='auto';vm.runInContext('engineChanged()',f.context);
 assert.equal(f.nodes.memoryMode.value,'auto');assert.equal(f.nodes.memoryMode.disabled,false);assert.equal(f.nodes.compactVerification.hidden,true);assert.equal(f.plans(),2);
});
test('reselecting compact preserves the original explicit disk preference',()=>{
 const f=setup('disk');vm.runInContext('engineChanged();engineChanged()',f.context);f.nodes.engineSelect.value='ycruncher';vm.runInContext('engineChanged()',f.context);assert.equal(f.nodes.memoryMode.value,'disk');
});
test('RAM-aware Auto recovery changes settings and plans without starting a calculation',()=>{
 const f=setup('ram');vm.runInContext('engineChanged()',f.context);f.state.planBlocked=true;
 vm.runInContext('useRamAwareAuto()',f.context);assert.equal(f.nodes.engineSelect.value,'auto');assert.equal(f.nodes.memoryMode.value,'auto');assert.equal(f.state.planBlocked,false);assert.equal(f.nodes.memoryMode.disabled,false);assert.equal(f.plans(),2);
});
