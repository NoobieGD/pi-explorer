/* Pi Explorer browser engine. No network or native-server dependencies. */
'use strict';
const NUMBER_INFO={"pi": {"label": "Pi", "symbol": "π", "integer": 3, "prefix": "14159265358979323846264338327950288419716939937510", "native": "pi", "algorithm": "chudnovsky"}, "e": {"label": "Euler's number", "symbol": "e", "integer": 2, "prefix": "71828182845904523536028747135266249775724709369995", "native": "e", "algorithm": "exp(1)"}, "sqrt2": {"label": "Square root of 2", "symbol": "√2", "integer": 1, "prefix": "41421356237309504880168872420969807856967187537694", "native": "sqrt:2", "algorithm": "newton", "radicand": 2}, "sqrt3": {"label": "Square root of 3", "symbol": "√3", "integer": 1, "prefix": "73205080756887729352744634150587236694280525381038", "native": "sqrt:3", "algorithm": "newton", "radicand": 3}, "sqrt5": {"label": "Square root of 5", "symbol": "√5", "integer": 2, "prefix": "23606797749978969640917366873127623544061835961152", "native": "sqrt:5", "algorithm": "newton", "radicand": 5}, "phi": {"label": "Golden ratio", "symbol": "φ", "integer": 1, "prefix": "61803398874989484820458683436563811772030917980576", "native": "phi", "algorithm": "newton"}};
const PI_PREFIX='14159265358979323846264338327950288419716939937510';
const pause=()=>new Promise(resolve=>setTimeout(resolve,0));
function isqrt(n){if(n<0n)throw Error('Negative square root');if(n<2n)return n;let x=1n<<BigInt(Math.ceil(n.toString(2).length/2));for(;;){const y=(x+n/x)>>1n;if(y>=x)return x;x=y;}}
function computePi(count,progress=()=>{}){
 if(!Number.isSafeInteger(count)||count<1)throw Error('Enter a positive count this browser can represent exactly. Use the desktop native engine for larger counts.');
 const n=count+32,terms=Math.floor(n/14)+1,C=640320n**3n/24n;let completed=0,next=0;
 function split(a,b){
  if(b-a===1){const k=BigInt(a),p=a===0?1n:(6n*k-5n)*(2n*k-1n)*(6n*k-1n),q=a===0?1n:k*k*k*C;let t=p*(13591409n+545140134n*k);if(a%2)t=-t;
   if(++completed>=next){progress(.03+.6*completed/terms,'Chudnovsky · binary splitting');next=completed+Math.max(1,Math.floor(terms/32));}return[p,q,t];}
  const m=Math.floor((a+b)/2),[p1,q1,t1]=split(a,m),[p2,q2,t2]=split(m,b);return[p1*p2,q1*q2,t1*q2+p1*t2];
 }
 const [,q,t]=split(0,terms);progress(.69,'Computing exact integer square root');const root=isqrt(10005n*10n**BigInt(2*n));progress(.87,'Final division and decimal conversion');
 const raw=(q*426880n*root/t).toString(),digits=raw.slice(1,count+1);
 if(raw.length!==n+1||!digits.startsWith(PI_PREFIX.slice(0,Math.min(50,count))))throw Error('Pi verification failed');
 return digits;
}
function computeConstant(count,constant='pi',progress=()=>{}){
 if(!NUMBER_INFO[constant])throw Error('Unknown constant');
 if(constant==='pi')return computePi(count,progress);
 if(!Number.isSafeInteger(count)||count<1)throw Error('Enter a positive exact digit count.');
 const spec=NUMBER_INFO[constant],scale=10n**BigInt(count);let result;
 if(constant!=='e'){
  progress(.1,'Exact integer square root');const root=isqrt(BigInt(constant==='phi'?5:spec.radicand)*scale*scale);result=constant==='phi'?(root+scale)/2n:root;
 }else{
  const target=count+32;let n=Math.max(8,Math.floor(target/Math.max(1,Math.log10(Math.max(10,target)))*1.3));
  const logFactorial=n=>(n+.5)*Math.log(n)-n+.5*Math.log(2*Math.PI)+1/(12*n);
  while(logFactorial(n)/Math.LN10<target)n=Math.max(n+1,Math.floor(n*1.1));
  for(let attempt=0;attempt<4;attempt++){
   let completed=0;const update=Math.max(1,Math.floor(n/40));
   function split(a,b){if(b-a===1){if(++completed%update===0)progress(.03+.7*completed/n,'Factorial series · binary splitting');return[1n,BigInt(a)];}const mid=Math.floor((a+b)/2),[p,q]=split(a,mid),[r,s]=split(mid,b);return[p*s+r,q*s];}
   const[p,q]=split(1,n+1),N=BigInt(n),lower=scale*(p+q)/q,upper=(scale*(N*(p+q)+1n)-1n)/(N*q);
   if(lower===upper){result=lower;break;}n+=Math.max(32,Math.floor(n/10));
  }
  if(result===undefined)throw Error('Remainder did not certify all digits');
 }
 progress(.9,'Converting certified decimal digits');const raw=result.toString(),digits=raw.slice(1);
 if(raw.length!==count+1||Number(raw[0])!==spec.integer||!digits.startsWith(spec.prefix.slice(0,Math.min(50,count))))throw Error('Constant verification failed');
 return digits;
}
function encodeLetters(digits,scheme='mod26',alignment=0){
 const step=scheme==='ascii'?3:2,length=Math.max(0,Math.floor((digits.length-alignment)/step)),out=new Uint8Array(length);
 for(let j=0,i=alignment;j<length;j++,i+=step){let value=(digits.charCodeAt(i)-48)*10+digits.charCodeAt(i+1)-48;if(step===3)value=value*10+digits.charCodeAt(i+2)-48;
  out[j]=scheme==='mod26'?65+value%26:scheme==='a1z26'?(value>=1&&value<=26?64+value:46):(value>=32&&value<=126?value:46);}
 return new TextDecoder().decode(out);
}
function encodeBits(digits,rule='threshold'){
 const out=new Uint8Array(digits.length);for(let i=0;i<digits.length;i++){const v=digits.charCodeAt(i)-48;out[i]=(rule==='parity'?v%2:v>=5)?49:48;}return new TextDecoder().decode(out);
}
function findMatches(data,query,limit=300){const matches=[];let at=0;while(matches.length<limit){const p=data.indexOf(query,at);if(p<0)return[matches,false];matches.push(p);at=p+1;}return[matches,data.indexOf(query,at)>=0];}
async function findShapes(digits,rows,widths,rule='threshold',limit=60,progress=()=>{},cancelled=()=>false){
 if(!rows.length||rows.length>24)throw Error('Choose a shape of 1–24 rows.');const h=rows.length,w=rows[0].length,n=digits.length;
 if(w<1||w>24||rows.some(row=>row.length!==w||/[^01?]/.test(row))||!rows.some(row=>/[01]/.test(row)))throw Error('Invalid pixel pattern.');
 widths=[...new Set(widths)].filter(v=>Number.isInteger(v)&&v>=w&&v<=4096).sort((a,b)=>a-b);if(!widths.length)throw Error('Row width must fit the shape.');
 const length=Math.ceil(n/32)+2,source=new Uint32Array(length),masks=new Map();
 for(let i=0;i<n;i++){const v=digits.charCodeAt(i)-48;if(rule==='parity'?v%2:v>=5)source[i>>>5]|=1<<(i&31);}
 for(const row of new Set(rows)){
  const mask=new Uint32Array(length);
  for(let j=0;j<length;j++){let value=0xffffffff;for(let x=0;x<w;x++){if(row[x]==='?')continue;const a=source[j]||0,b=source[j+1]||0,part=x===0?a:(a>>>x)|(b<<(32-x));value&=row[x]==='1'?part:~part;if(!value)break;}mask[j]=value>>>0;}
  masks.set(row,mask);await pause();if(cancelled())throw Error('Search cancelled');
 }
 const output=[];
 for(let wi=0;wi<widths.length;wi++){
  if(cancelled())throw Error('Search cancelled');const stride=widths[wi],valid=n-(h-1)*stride-w+1;
  progress(wi/widths.length,'Searching row width '+stride);if(valid<=0)continue;
  const rowInfo=rows.map((row,y)=>{const offset=y*stride;return{mask:masks.get(row),word:offset>>>5,shift:offset&31};});
  const words=Math.ceil(valid/32);
  for(let j=0;j<words;j++){
   let candidates=0xffffffff;
   for(const {mask,word,shift} of rowInfo){const a=mask[j+word]||0,b=mask[j+word+1]||0;candidates&=shift===0?a:(a>>>shift)|(b<<(32-shift));if(!candidates)break;}
   if(j===words-1&&valid%32)candidates&=(2**(valid%32)-1);
   candidates>>>=0;
   while(candidates){const bit=31-Math.clz32(candidates&-candidates),index=j*32+bit;candidates=(candidates&(candidates-1))>>>0;
    if(index%stride+w<=stride){output.push({index,position:index+1,width:stride,height:h,shapeWidth:w});if(output.length>=limit)return[output.sort((a,b)=>a.index-b.index||a.width-b.width),true];}}
  }
  await pause();
 }
 return[output.sort((a,b)=>a.index-b.index||a.width-b.width),false];
}
async function statistics(digits){
 const counts=Array(10).fill(0),n=digits.length;let run=0,last='',longest={digit:'',length:0,position:0};
 for(let i=0;i<n;i++){const c=digits[i];counts[c.charCodeAt(0)-48]++;run=c===last?run+1:1;last=c;if(run>longest.length)longest={digit:c,length:run,position:i-run+2};}
 const entropy=counts.reduce((s,v)=>v?s-v/n*Math.log2(v/n):s,0),chiSquare=n?counts.reduce((s,v)=>s+(v-n/10)**2/(n/10),0):0;
 let sha256='Unavailable in this browser context';if(globalThis.crypto?.subtle){const hash=await crypto.subtle.digest('SHA-256',new TextEncoder().encode(digits));sha256=[...new Uint8Array(hash)].map(b=>b.toString(16).padStart(2,'0')).join('');}
 return{counts,entropy,chiSquare,longestRun:longest,sha256,count:n};
}
if(typeof module!=='undefined'&&module.exports)module.exports={computePi,computeConstant,NUMBER_INFO,isqrt,encodeLetters,encodeBits,findMatches,findShapes,statistics};
if(typeof self!=='undefined'&&typeof self.postMessage==='function'){
 let digits='',constant='pi',derived=new Map(),jobs=new Map();
 const getData=(mode='digits',scheme='mod26',rule='threshold',alignment=0)=>{
  if(mode==='digits'||mode==='colors')return digits;const key=[mode,scheme,rule,alignment].join(':');
  if(!derived.has(key)){if(derived.size>=4)derived.clear();derived.set(key,mode==='text'?encodeLetters(digits,scheme,alignment):encodeBits(digits,rule));}return derived.get(key);
 };
 const publish=job=>self.postMessage({type:'job',job:{...job,cancel:undefined}});
 async function search(job,payload){
  try{
   const started=performance.now(),mode=payload.mode||'digits',scheme=payload.scheme||'mod26',rule=payload.rule||'threshold',alignment=payload.alignment||0;
   let query=String(payload.query||'').trim(),matches,capped,scanned=digits.length;
   if(mode==='shape'){
    const rows=payload.rows;let widths=[+payload.width];if(payload.sweep){const lo=Math.max(rows[0].length,+payload.minWidth),hi=Math.min(1024,+payload.maxWidth);widths=Array.from({length:Math.max(0,hi-lo+1)},(_,i)=>lo+i);}
    [matches,capped]=await findShapes(digits,rows,widths,rule,60,(p,m)=>{job.progress=p;job.message=m;publish(job);},()=>job.cancel);query=rows.join('/');
   }else{
    if(mode==='text'){if(/[^\x20-\x7e]/.test(query))throw Error('Use ASCII text.');if(scheme!=='ascii')query=query.toUpperCase();}else if(!/^\d+$/.test(query))throw Error('Enter digits 0–9.');
    if(!query||query.length>2048)throw Error('Enter a pattern of 1–2,048 characters.');
    const data=getData(mode,scheme,rule,alignment);scanned=data.length;let positions;[positions,capped]=findMatches(data,query,300);
    const step=scheme==='ascii'?3:2;matches=positions.map(p=>({index:p,position:mode==='text'?p*step+alignment+1:p+1,unitPosition:p+1,length:query.length}));
   }
   Object.assign(job,{status:'done',progress:1,matches,capped,query,scanned,message:'Search complete',seconds:(performance.now()-started)/1000});publish(job);
  }catch(error){Object.assign(job,{status:job.cancel?'cancelled':'error',error:error.message,message:error.message});publish(job);}
 }
 self.onmessage=async({data:{id,cmd,args={}}})=>{
  try{
   let result;
   if(cmd==='init'||cmd==='setDigits'){digits=args.digits;constant=args.constant||'pi';if(!NUMBER_INFO[constant])throw Error('Unknown constant');derived.clear();result={count:digits.length};}
   else if(cmd==='compute'){const started=performance.now();const computed=computeConstant(args.count,args.constant||'pi',(progress,message)=>self.postMessage({type:'computeProgress',progress,message}));result={digits:computed,seconds:(performance.now()-started)/1000};}
   else if(cmd==='digits'){const data=getData(args.mode,args.scheme,args.rule,+args.alignment||0),start=Math.max(0,+args.start||0),count=Math.min(2000000,+args.count||10000);result={start,total:data.length,data:data.slice(start,start+count)};}
   else if(cmd==='tile'){
    const p=Object.fromEntries(Object.entries(args).map(([k,v])=>[k,['mode','scheme','rule'].includes(k)?v:+v]));
    const step=p.mode==='text'?(p.scheme==='ascii'?3:2):1,alignment=p.mode==='text'?p.alignment||0:0,total=Math.floor((digits.length-alignment)/step),out=new Uint8Array(p.rows*p.cols);out.fill(32);
    for(let r=0;r<p.rows;r++)for(let c=0;c<p.cols;c++){
     const index=(p.rowStart+r*p.rowStep)*p.gridWidth+p.colStart+c*p.colStep;if(index>=total)continue;const at=alignment+index*step,v=digits.charCodeAt(at)-48;let code=v+48;
     if(p.mode==='text'){const pair=v*10+digits.charCodeAt(at+1)-48;if(p.scheme==='ascii'){const n=pair*10+digits.charCodeAt(at+2)-48;code=n>=32&&n<=126?n:46;}else code=p.scheme==='a1z26'?(pair>=1&&pair<=26?pair+64:46):65+pair%26;}
     else if(p.mode==='binary')code=(p.rule==='parity'?v%2:v>=5)?49:48;out[r*p.cols+c]=code;
    }
    result={...p,total,data:new TextDecoder().decode(out)};
   }
   else if(cmd==='export')result=NUMBER_INFO[constant].integer+'.'+digits;
   else if(cmd==='stats')result=await statistics(digits);
   else if(cmd==='search'){
    if(!digits.length)throw Error('Compute or import digits first.');if([...jobs.values()].filter(j=>j.status==='running').length>=2)throw Error('Wait for the current searches.');
    const job={id:Math.random().toString(36).slice(2),status:'running',progress:0,message:'Preparing search',cancel:false};jobs.set(job.id,job);
    for(const [key,j] of jobs)if(jobs.size>24&&j.status!=='running')jobs.delete(key);
    result={id:job.id};setTimeout(()=>search(job,args),0);
   }else if(cmd==='cancelSearch'){const job=jobs.get(args.id);if(job)job.cancel=true;result={ok:true};}
   else throw Error('Unknown browser operation');
   self.postMessage({id,result});
  }catch(error){self.postMessage({id,error:error.message});}
 };
}
