const test=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const E=require('../portable/portable-engine.js');
const root=path.resolve(__dirname,'..');
function readExistingSeed(){
 const dir=path.join(root,'data'),seed=path.join(dir,'pi-5000000.txt');
 if(fs.existsSync(seed))return fs.readFileSync(seed,'ascii');
 const file=fs.readdirSync(dir).filter(n=>/^pi-\d+\.txt$/.test(n)).map(n=>path.join(dir,n)).find(p=>fs.statSync(p).size>=5000000);
 const fd=fs.openSync(file,'r'),head=Buffer.alloc(2),out=Buffer.alloc(5000000);
 try{fs.readSync(fd,head,0,2,0);fs.readSync(fd,out,0,out.length,head.toString()==='3.'?2:0);return out.toString('ascii');}finally{fs.closeSync(fd);}
}
const pi=readExistingSeed();
test('browser exact Chudnovsky agrees with native digits',()=>{for(const n of [1,50,10000,100000])assert.equal(E.computePi(n),pi.slice(0,n));});
test('video words, positions, encodings and overlapping matches',()=>{
 const text=E.encodeLetters(pi.slice(0,200000));assert.equal(text.indexOf('PIE')+1,10962);assert.equal(text.indexOf('CAT')+1,22731);assert.equal(text.indexOf('DOG')+1,44145);assert.equal(text.indexOf('MATH')+1,91682);
 assert.deepEqual(E.findMatches('1111','11'),[[0,1,2],false]);assert.equal(E.encodeBits('0123456789'),'0000011111');assert.equal(E.encodeBits('0123456789','parity'),'0101010101');assert.equal(E.encodeLetters('072101108108111','ascii'),'Hello');
});
test('32-bit pixel matcher equals brute-force including word and row boundaries',async()=>{
 let seed=14159;const random=()=>{seed=(seed*1664525+1013904223)>>>0;return seed/2**32;};
 for(let pass=0;pass<18;pass++){
  const digits=Array.from({length:450},()=>random()>.5?'8':'1').join(''),rows=Array.from({length:3},()=>Array.from({length:3},()=>['0','1','?'][Math.floor(random()*3)]).join(''));
  const expected=[];for(const width of [5,8,33,67])for(let p=0;p+2*width+3<=digits.length;p++){if(p%width+3>width)continue;if(rows.every((r,y)=>[...r].every((v,x)=>v==='?'||(digits[p+y*width+x]==='8'?'1':'0')===v)))expected.push([p,width]);}
  const [got,capped]=await E.findShapes(digits,rows,[5,8,33,67],'threshold',10000);assert.equal(capped,false);assert.deepEqual(got.map(m=>[m.index,m.width]),expected.sort((a,b)=>a[0]-b[0]||a[1]-b[1]));
 }
});
test('real five-million-digit pi symbol matches desktop results',async()=>{
 const [result,capped]=await E.findShapes(pi,['11111','01010','01010','01010','01011'],Array.from({length:315},(_,i)=>i+6));assert.equal(capped,false);assert.equal(result.length,47);assert.equal(result[0].position,149865);assert.equal(result[0].width,127);
});
test('statistics count exact digits and hash',async()=>{const s=await E.statistics('0123456789'.repeat(10));assert.deepEqual(s.counts,Array(10).fill(10));assert.equal(s.chiSquare,0);assert.ok(Math.abs(s.entropy-Math.log2(10))<1e-12);});
