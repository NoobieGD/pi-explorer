const test=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs'),path=require('node:path');
const scope=vm.createContext({window:{},Map,Math,performance,URLSearchParams,console});vm.runInContext(fs.readFileSync(path.join(__dirname,'../app/viewport.js'),'utf8'),scope);const View=scope.window.PiViewport;
test('billion-digit camera requests a bounded sampled tile at extreme zoom',()=>{
 const view=new View(()=>{},()=>{});
 for(const cols of [4,200,4096])for(const scale of [.035,.1,1,22])for(const mode of ['digits','text','binary','colors']){
  const s={count:1000000000,view:mode,scheme:'mod26',alignment:0,cols,scale,tx:-200,ty:-500000*22*scale};const d=view.descriptor(s,1600,900,13,22,'test');if(!d)continue;
  assert.ok(d.params.rows*d.params.cols<1000000);assert.ok(d.params.colStart+(d.params.cols-1)*d.params.colStep<cols);
 }
});
test('sample lookup preserves absolute digit positions beyond 32-bit pixel coordinates',()=>{
 const v=new View(()=>{},()=>{});v.tile={dataKey:'x',gridWidth:200,rowStart:4000000,colStart:10,rowStep:2,colStep:3,rows:2,cols:3,data:'123456'};
 assert.equal(v.charAt(4000000*200+10,'x'),'1');assert.equal(v.charAt(4000002*200+16,'x'),'6');assert.equal(v.charAt(4000001*200+10,'x'),'');
});
test('four text detail levels crossfade continuously without a blank interval',()=>{
 const v=new View(()=>{},()=>{});let previous=v.levels(.1);const dominant=new Set();
 for(let x=.101;x<10;x+=.001){const a=v.levels(x);assert.ok(Math.abs(Object.values(a).reduce((sum,n)=>sum+n,0)-1)<1e-10);for(const key of Object.keys(a))assert.ok(Math.abs(a[key]-previous[key])<.01);dominant.add(Object.entries(a).sort((a,b)=>b[1]-a[1])[0][0]);previous=a;}
 assert.equal(dominant.size,4);assert.equal(v.detail(.5,'text'),'ROW OVERVIEW');assert.equal(v.detail(9,'digits'),'FULL GLYPHS');
});
test('tile history obeys its memory budget and preserves the visible tile',()=>{
 const v=new View(()=>{},()=>{});for(let i=0;i<8;i++){const t={data:'123',rasters:new Map([['fine',{width:1024,height:1024}]])};v.cache.set(String(i),t);v.tile=t;}v.trim();assert.ok(v.cache.size<8);assert.ok([...v.cache.values()].includes(v.tile));
});
