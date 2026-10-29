'use strict';
const $=id=>document.getElementById(id);
const NUMBERS={"pi": {"label": "Pi", "symbol": "π", "integer": 3, "prefix": "14159265358979323846264338327950288419716939937510", "native": "pi", "algorithm": "chudnovsky"}, "e": {"label": "Euler's number", "symbol": "e", "integer": 2, "prefix": "71828182845904523536028747135266249775724709369995", "native": "e", "algorithm": "exp(1)"}, "sqrt2": {"label": "Square root of 2", "symbol": "√2", "integer": 1, "prefix": "41421356237309504880168872420969807856967187537694", "native": "sqrt:2", "algorithm": "newton", "radicand": 2}, "sqrt3": {"label": "Square root of 3", "symbol": "√3", "integer": 1, "prefix": "73205080756887729352744634150587236694280525381038", "native": "sqrt:3", "algorithm": "newton", "radicand": 3}, "sqrt5": {"label": "Square root of 5", "symbol": "√5", "integer": 2, "prefix": "23606797749978969640917366873127623544061835961152", "native": "sqrt:5", "algorithm": "newton", "radicand": 5}, "phi": {"label": "Golden ratio", "symbol": "φ", "integer": 1, "prefix": "61803398874989484820458683436563811772030917980576", "native": "phi", "algorithm": "newton"}};
const targetConstant=()=>$('constantSelect')?.value||'pi';
const fmt=n=>Math.round(n).toLocaleString('en-US');
const palette=['#ef5350','#ff9e40','#f6d85d','#78cb70','#39bba0','#42b9d5','#5486e8','#a67ce8','#e578b3','#e4e7ee'];
function syncNumberOptions(){
 const constant=targetConstant();
 for(const option of $('engineSelect').options)if(['chudnovsky','tachuspi','compact'].includes(option.value))option.disabled=constant!=='pi';
 if($('engineSelect').selectedOptions[0]?.disabled)$('engineSelect').value='auto';
 const packed=$('engineSelect').querySelector('[value="ycruncher-low"]');if(packed)packed.textContent=constant==='pi'?'Reduced disk · Chudnovsky + packed YCD':'Native · packed YCD output';
}
const state={constant:'pi',constantsSupported:false,count:0,token:'',view:'digits',searchMode:'digits',scheme:'mod26',alignment:0,rule:'threshold',cols:200,
 scale:1,tx:35,ty:160,chunk:'',chunkStart:0,chunkKey:'',total:0,loading:false,dirty:true,
 matches:[],active:-1,query:'',shapeRows:[],job:null,computing:false,shapeSize:6,shape:[],sound:true,volume:.24,
 bookmarks:[],history:[],fps:0,fetchTicket:0,fetchWanted:null,stats:null,shuttingDown:false};
try{const prefs=JSON.parse(localStorage.getItem('pi-preferences')||'{}');for(const key of ['sound','volume','bookmarks','history','rule'])if(key in prefs)state[key]=prefs[key];}catch{}
state.bookmarks=Array.isArray(state.bookmarks)?state.bookmarks:[];
const canvas=$('piCanvas'),area=$('canvasArea'),ctx=canvas.getContext('2d',{alpha:false});
let W=1,H=1,DPR=1,scheduled=false,drag=null,pointerMoved=false,searchAbort=null,toastTimer,audio;
const cache=new Map();
const viewport=new PiViewport(api,invalidate);
const computeLive=new PiComputeLive($);
document.fonts?.ready.then(()=>viewport.resetGlyphs());
function savePrefs(){try{localStorage.setItem('pi-preferences',JSON.stringify({sound:state.sound,volume:state.volume,bookmarks:state.bookmarks,history:state.history,rule:state.rule}));}catch{}}
function toast(message){$('toast').textContent=message;$('toast').classList.add('visible');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('toast').classList.remove('visible'),3500);}
function sfx(name='click'){
 if(!state.sound||state.volume<=0)return;
 try{
  audio ||= new (window.AudioContext||window.webkitAudioContext)();if(audio.state==='suspended')audio.resume();
  const now=audio.currentTime;
  const notes={click:[650,870],found:[523.25,659.25,783.99],compute:[220,330,440],empty:[220,196],zoom:[340],bookmark:[880,1174]};
  (notes[name]||notes.click).forEach((freq,i)=>{const osc=audio.createOscillator(),gain=audio.createGain();osc.type=name==='found'?'sine':'triangle';osc.frequency.setValueAtTime(freq,now+i*.085);gain.gain.setValueAtTime(0,now+i*.085);gain.gain.linearRampToValueAtTime(state.volume*.12,now+i*.085+.008);gain.gain.exponentialRampToValueAtTime(.0001,now+i*.085+.18);osc.connect(gain).connect(audio.destination);osc.start(now+i*.085);osc.stop(now+i*.085+.2);});
 }catch{}
}
let sessionRefresh=null;
async function refreshSession(){
 if(!sessionRefresh)sessionRefresh=(async()=>{const response=await fetch('/api/status?session='+Date.now(),{cache:'no-store'});if(!response.ok)throw Error('Local engine is unavailable. Reopen Start Pi Explorer.');const status=await response.json();if(!status.token)throw Error('Local engine did not provide a session.');state.token=status.token;return status;})().finally(()=>{sessionRefresh=null;});
 return sessionRefresh;
}
async function api(path,body){
 if(window.PiLocalApi)return window.PiLocalApi.request(path,body);
 if(body!==undefined&&!state.token)await refreshSession();
 for(let attempt=0;attempt<2;attempt++){
  const response=await fetch('/api/'+path,body===undefined?{cache:'no-store'}:{method:'POST',cache:'no-store',headers:{'Content-Type':'application/json','X-Pi-Token':state.token},body:JSON.stringify(body)});
  let data;try{data=await response.json();}catch{if(body===undefined&&attempt===0)continue;throw Error('Could not read the local engine response. Reopen Start Pi Explorer.');}
  if(response.status===403&&body!==undefined&&attempt===0&&(data.code==='SESSION_EXPIRED'||/refresh|session/i.test(data.error||''))){await refreshSession();state.shuttingDown=false;continue;}
  if(!response.ok||data.error)throw Error(data.error||'Local engine error');
  return data;
 }
 throw Error('Could not reconnect to the local engine. Reopen Start Pi Explorer.');
}
function computeLimit(){return window.PiLocalApi?.maxComputeDigits??state.maxDigits??Infinity;}
function readComputeCount(){
 const text=$('digitCount').value.trim().replace(/[,\s_]/g,'');
 if(!/^[0-9]+$/.test(text)||BigInt(text)<1n)throw Error('Enter a positive whole number of decimal places.');
 return BigInt(text).toString();
}
function resourceText(plan){
 const mib=n=>Math.ceil(n/1048576).toLocaleString('en-US')+' MiB',gib=n=>(n/1073741824).toFixed(2)+' GiB';
 if(plan.mode==='cache')return'Already cached · no new calculation or temporary files.';
 if(plan.method==='tachuspi')return'TachusPI · packed output\nRAM budget: '+mib(plan.ramBudgetBytes)+'\n'+(plan.mode==='disk'?'Trial disk budget: ':'Saved digits: ')+gib(plan.peakDiskBytes)+' + 2 GiB reserve.\n'+plan.message;
 if(plan.method==='compact')return plan.message+'\nRAM required: '+gib(plan.estimatedBytes)+' · budget '+mib(plan.ramBudgetBytes)+'\nCurrent RAM fits up to '+fmt(plan.compactMaxDigitsForRam||0)+' compact digits.';
 if(plan.lowDisk)return'Reduced Chudnovsky · direct packed YCD output\nSaved digits: '+gib(plan.outputBytes)+' (no text expansion)\nConservative disk budget: '+gib(plan.peakDiskBytes)+' + 2 GiB reserve.\nSlower arithmetic; exact output verification retained.';
 if(plan.mode==='disk')return'RAM budget: '+mib(plan.ramBudgetBytes)+' · disk blocks\nTemporary disk cap: '+gib(plan.peakDiskBytes)+'\nSaved digits: '+mib(plan.outputBytes)+' · scratch cleared after use\n'+(plan.requiresElevation?'Windows approval required for the calculator.':'');
 return'Fits in RAM · budget '+mib(plan.ramBudgetBytes)+'\nSaved digits: '+mib(plan.outputBytes)+' · 2 GiB disk reserve';
}
let planTicket=0,planTimer;
async function refreshPlan(){
 if(window.PiLocalApi){$('memoryControls').hidden=true;return;}
 const ticket=++planTicket;
 try{const count=readComputeCount();
  const plan=await api('plan?'+new URLSearchParams({count,constant:targetConstant(),method:$('engineSelect').value,storageMode:$('memoryMode').value,force:$('forceCompute').checked}));
  if(ticket!==planTicket)return;state.resourcePlan=plan;state.planBlocked=plan.launchable===false;$('resourcePlan').textContent=resourceText(plan);$('resourcePlan').classList.toggle('error',state.planBlocked);if(!state.computing)$('computeBtn').disabled=state.planBlocked;
 }catch(error){if(ticket===planTicket){state.planBlocked=true;if(!state.computing)$('computeBtn').disabled=state.planBlocked;$('resourcePlan').textContent=error.message;$('resourcePlan').classList.add('error');}}
}
function engineChanged(){
 const compact=$('engineSelect').value==='compact';$('compactVerification').hidden=!compact;
 if(compact){
  if(!state.compactActive)state.memoryModeBeforeCompact=$('memoryMode').value;
  state.compactActive=true;$('memoryMode').value='ram';
 }else if(state.compactActive){
  $('memoryMode').value=state.memoryModeBeforeCompact||'auto';state.compactActive=false;delete state.memoryModeBeforeCompact;
 }
 $('memoryMode').disabled=compact||state.computing;
 void refreshPlan();
}
function useRamAwareAuto(){
 $('engineSelect').value='auto';$('memoryMode').value='auto';
 state.compactActive=false;delete state.memoryModeBeforeCompact;state.planBlocked=false;
 engineChanged();toast('Auto uses RAM when it fits, otherwise disk-backed blocks. No calculation started.');
}
async function checkCompactTarget(){
 const button=$('compactCheckBtn');button.disabled=true;
 try{const report=await api('compact-check?count=200000000000');
  $('compactCheckResult').textContent=(report.verifiedUnderBudget?'VERIFIED':'NOT VERIFIED')+' · no calculation started\nText output: '+(report.textOutputBytes/1073741824).toFixed(2)+' GiB\nRemaining budget: '+(report.temporaryBudgetAfterTextBytes/1073741824).toFixed(2)+' GiB\nNo proven peak-workspace bound or disk-backed compact engine is available.';
 }catch(error){$('compactCheckResult').textContent=error.message;}finally{button.disabled=false;}
}
function geometry(){const pixels=state.view==='colors'||state.view==='binary';return pixels?{cw:12,ch:12}:{cw:13,ch:22};}
function dataKey(){return [state.view,state.scheme,state.rule,state.alignment,state.count,state.datasetId].join(':');}
function totalUnits(){return state.view==='text'?Math.floor((state.count-state.alignment)/(state.scheme==='ascii'?3:2)):state.count;}
function unitsToDigit(index){return state.view==='text'?index*(state.scheme==='ascii'?3:2)+state.alignment:index;}
function digitToUnits(index){return state.view==='text'?Math.floor((index-state.alignment)/(state.scheme==='ascii'?3:2)):index;}
function invalidate(){state.dirty=true;if(!scheduled){scheduled=true;requestAnimationFrame(render);}}
function resize(){const rect=area.getBoundingClientRect();W=rect.width;H=rect.height;DPR=Math.min(window.devicePixelRatio||1,2);canvas.width=Math.round(W*DPR);canvas.height=Math.round(H*DPR);ctx.setTransform(DPR,0,0,DPR,0,0);invalidate();}
new ResizeObserver(resize).observe(area);
function clampCamera(){const {cw,ch}=geometry();const total=totalUnits();const contentHeight=Math.ceil(total/state.cols)*ch*state.scale;state.ty=Math.min(180,Math.max(Math.min(180,H-80-contentHeight),state.ty));state.tx=Math.min(W-35,Math.max(35-state.cols*cw*state.scale,state.tx));}
function fit(reset=true){const {cw}=geometry();state.scale=Math.max(.035,Math.min(3,(W-80)/(state.cols*cw)));state.tx=(W-state.cols*cw*state.scale)/2;if(reset)state.ty=158;clampCamera();invalidate();}
function zoom(factor,x=W/2,y=H/2){const previous=state.scale;state.scale=Math.max(.035,Math.min(22,state.scale*factor));const actual=state.scale/previous;state.tx=x-(x-state.tx)*actual;state.ty=y-(y-state.ty)*actual;clampCamera();invalidate();}
function visibleRange(){const {cw,ch}=geometry(),cellH=ch*state.scale;const first=Math.max(0,Math.floor(-state.ty/cellH)-1),last=Math.min(Math.ceil(totalUnits()/state.cols),Math.ceil((H-state.ty)/cellH)+1);return{first,last,start:first*state.cols,end:Math.min(totalUnits(),last*state.cols)};}
function render(){
 scheduled=false;state.dirty=false;
 ctx.setTransform(DPR,0,0,DPR,0,0);ctx.fillStyle='#080a10';ctx.fillRect(0,0,W,H);
 const {cw,ch}=geometry(),sx=cw*state.scale,sy=ch*state.scale;
 const range=visibleRange();
 // Quiet Cartesian guides keep a sense of scale when the grid is distant.
 ctx.strokeStyle='#22273533';ctx.lineWidth=1;ctx.beginPath();
 for(let x=((state.tx%100)+100)%100;x<W;x+=100){ctx.moveTo(x,0);ctx.lineTo(x,H);}for(let y=((state.ty%100)+100)%100;y<H;y+=100){ctx.moveTo(0,y);ctx.lineTo(W,y);}ctx.stroke();
 viewport.draw(ctx,state,W,H,cw,ch,dataKey());
 if(sy>7){ctx.font='7px JetBrains,monospace';ctx.fillStyle='#45526a';ctx.textAlign='right';for(let row=range.first;row<range.last;row++){if(row%Math.max(1,Math.ceil(35/sy))===0)ctx.fillText(fmt(unitsToDigit(row*state.cols)+1),state.tx-12,state.ty+row*sy+sy/2);}}
 drawHighlights(sx,sy);
 // Faint boundary at the finite frontier.
 const bottom=state.ty+Math.ceil(totalUnits()/state.cols)*sy;
 if(state.count&&bottom>0&&bottom<H){ctx.strokeStyle='#917944';ctx.beginPath();ctx.moveTo(state.tx,bottom+4);ctx.lineTo(state.tx+state.cols*sx,bottom+4);ctx.stroke();ctx.fillStyle='#8b7a55';ctx.font='9px JetBrains, monospace';ctx.textAlign='left';ctx.fillText('END OF COMPUTED DIGITS · THE NUMBER CONTINUES',Math.max(20,state.tx),bottom+22);}
 $('zoomLabel').textContent=Math.round(state.scale*100)+'%';
 $('lodLabel').textContent=viewport.detail(sx,state.view);
 area.classList.toggle('close-up',state.scale>.3);
 const first=Math.max(0,Math.floor(-state.ty/sy)*state.cols);
 const position=Math.min(Math.max(0,state.count-1),unitsToDigit(first));
 $('navPosition').textContent='DIGIT '+fmt(position+1);$('positionSlider').value=state.count>1?position/(state.count-1)*1000000:0;
}
function drawHighlights(sx,sy){
 const active=state.matches[state.active];if(!active)return;
 const shape=active.shapeWidth!==undefined;
 const index=shape?active.index:digitToUnits(active.position-1);
 const row=Math.floor(index/state.cols),col=index%state.cols;
 const x=state.tx+col*sx,y=state.ty+row*sy;
 ctx.save();ctx.shadowColor='#e4bf7366';ctx.shadowBlur=15;ctx.fillStyle='#e4bf7315';ctx.fillRect(0,y,W,sy*(shape?active.height:1));ctx.shadowBlur=0;
 ctx.strokeStyle='#bca06377';ctx.lineWidth=1;ctx.beginPath();ctx.moveTo(0,y-.5);ctx.lineTo(W,y-.5);ctx.moveTo(0,y+sy*(shape?active.height:1)+.5);ctx.lineTo(W,y+sy*(shape?active.height:1)+.5);ctx.stroke();
 if(shape){ctx.strokeStyle='#f2d18a';ctx.lineWidth=2;ctx.strokeRect(x-3,y-3,sx*active.shapeWidth+5,sy*active.height+5);ctx.fillStyle='#e4bf7322';ctx.fillRect(x,y,sx*active.shapeWidth,sy*active.height);}
 else{
  const unitLength=state.view==='text'?active.length:(state.searchMode==='text'?active.length*(state.scheme==='ascii'?3:2):active.length);
  for(let i=0;i<unitLength;i++){const p=index+i;const px=state.tx+(p%state.cols)*sx,py=state.ty+Math.floor(p/state.cols)*sy;ctx.fillStyle='#e4bf7318';ctx.fillRect(px,py,sx,sy);ctx.strokeStyle='#e4bf7377';ctx.lineWidth=.6;ctx.strokeRect(px,py,sx,sy);if(state.view==='digits'||state.view==='text'){const visibleChar=viewport.charAt(p,dataKey());if(visibleChar){ctx.fillStyle='#f7d888';ctx.shadowColor='#e4bf7388';ctx.shadowBlur=12;ctx.font=`${14*state.scale}px JetBrains, Consolas, monospace`;ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(visibleChar,px+sx/2,py+sy/2);ctx.shadowBlur=0;}}}
 }
 if(y>-50&&y<H){ctx.fillStyle='#e4bf73';ctx.font='9px JetBrains, monospace';ctx.textAlign='left';ctx.textBaseline='bottom';ctx.fillText('↳ DIGIT '+fmt(active.position),Math.max(20,Math.min(W-180,x)),y-10);}
 ctx.restore();
}
function flyTo(index,preferredScale,spanWidth=1,spanHeight=1){
 const {cw,ch}=geometry();const row=Math.floor(index/state.cols),col=index%state.cols;
 const targetScale=preferredScale??Math.max(state.scale,state.view==='text'?3.3:2.1);
 const targetX=Math.min(35,Math.max(W-state.cols*cw*targetScale-35,W/2-(col+spanWidth/2)*cw*targetScale));
 const targetY=H*.48-(row+spanHeight/2)*ch*targetScale;
 const from={tx:state.tx,ty:state.ty,scale:state.scale},start=performance.now(),duration=650;
 const reduce=matchMedia('(prefers-reduced-motion: reduce)').matches;
 function step(now){const t=reduce?1:Math.min(1,(now-start)/duration),e=1-Math.pow(1-t,3);state.tx=from.tx+(targetX-from.tx)*e;state.ty=from.ty+(targetY-from.ty)*e;state.scale=from.scale+(targetScale-from.scale)*e;clampCamera();invalidate();if(t<1)requestAnimationFrame(step);}
 requestAnimationFrame(step);
}
function setView(view,reset=true){
 const currentDigit=unitsToDigit(Math.max(0,Math.floor(-state.ty/(geometry().ch*state.scale))*state.cols));
 state.view=view;state.chunkKey='';
 document.querySelectorAll('[data-view]').forEach(b=>{b.classList.toggle('active',b.dataset.view===view);b.setAttribute('aria-selected',b.dataset.view===view);});
 const names={digits:'DECIMAL / BASE 10',text:state.scheme==='ascii'?'ASCII / THREE DIGITS':'LETTERS / DIGIT PAIRS',colors:'COLOR / TEN DIGITS',binary:state.rule==='threshold'?'PIXELS / THRESHOLD 5':'PIXELS / ODD & EVEN'};
 $('canvasMode').textContent=names[view];$('paletteLegend').style.opacity=view==='colors'?'1':'.5';
 if(reset){fit(false);const index=digitToUnits(currentDigit);state.ty=158-Math.floor(index/state.cols)*geometry().ch*state.scale;}
 clampCamera();invalidate();
}
function setSearchMode(mode){
 state.searchMode=mode;state.matches=[];state.active=-1;renderNotebook();document.querySelectorAll('[data-search]').forEach(b=>{b.classList.toggle('active',b.dataset.search===mode);b.setAttribute('aria-selected',b.dataset.search===mode);});
 $('queryPanel').hidden=mode==='shape';$('shapePanel').hidden=mode!=='shape';$('textOptions').hidden=mode!=='text';
 $('queryLabel').textContent=mode==='text'?'Find a word or message':'Find a sequence';$('queryInput').placeholder=mode==='text'?'e.g. CAT':'e.g. 12345';
 if(mode==='text'&&/^\d+$/.test($('queryInput').value))$('queryInput').value='CAT';if(mode==='digits'&&!/^\d+$/.test($('queryInput').value))$('queryInput').value='12345';
 $('encodingHint').textContent=mode==='text'?'Two digits → modulo 26 → one letter.':'Every match. Every position. Real digits.';
 setView(mode==='shape'?'binary':mode);updateProbability();sfx();
}
function getShape(){
 let rows=state.shape.map(r=>r.join(''));
 if($('cropShape').checked){
  let top=0,bottom=rows.length-1,left=rows[0].length-1,right=0;
  while(top<=bottom&&!rows[top].includes('1'))top++;while(bottom>=top&&!rows[bottom].includes('1'))bottom--;
  if(top>bottom)throw Error('Draw at least one white pixel.');
  for(let y=top;y<=bottom;y++)for(let x=0;x<rows[y].length;x++)if(rows[y][x]==='1'){left=Math.min(left,x);right=Math.max(right,x);}
  rows=rows.slice(top,bottom+1).map(r=>r.slice(left,right+1));
 }
 return rows;
}
function updateProbability(){
 try{
  let log10=0,label='';
  if(state.searchMode==='shape'){const rows=getShape();const bits=rows.length*rows[0].length;log10=bits*Math.log10(2);label=bits+' constrained pixels';}
  else if(state.searchMode==='text'){const n=$('queryInput').value.length;log10=n*Math.log10(state.scheme==='ascii'?1000:26);label=n+' letters';}
  else{const n=$('queryInput').value.replace(/\s/g,'').length;log10=n;label=n+' digits';}
  const odds=log10<7?fmt(10**log10):'10^'+log10.toFixed(1);
  $('probability').textContent=label+' · about 1 in '+odds+' per start'+(state.searchMode==='text'?' (approx.)':'')+'\nAssuming independent uniform digits.';
 }catch{$('probability').textContent='Draw a pattern to estimate its rarity.';}
}
function buildShape(n=6,pattern){
 state.shapeSize=n;state.shape=Array.from({length:n},()=>Array(n).fill('0'));
 if(pattern){const ph=pattern.length,pw=pattern[0].length,oy=Math.floor((n-ph)/2),ox=Math.floor((n-pw)/2);for(let y=0;y<ph&&y+oy<n;y++)for(let x=0;x<pw&&x+ox<n;x++)if(x+ox>=0&&y+oy>=0)state.shape[y+oy][x+ox]=pattern[y][x];}
 const grid=$('shapeGrid');grid.style.gridTemplateColumns=`repeat(${n},1fr)`;grid.innerHTML='';
 for(let y=0;y<n;y++)for(let x=0;x<n;x++){const b=document.createElement('button');b.className='shape-cell'+(state.shape[y][x]==='1'?' on':'');b.setAttribute('aria-label',`Pixel row ${y+1} column ${x+1}`);b.setAttribute('aria-pressed',state.shape[y][x]==='1');b.dataset.x=x;b.dataset.y=y;grid.append(b);}
 updateProbability();
}
const patterns={pi:['11111','01010','01010','01010','01011'],heart:['0110110','1111111','1111111','0111110','0011100','0001000'],smile:['011110','100001','101101','100001','101101','011110'],checker:['101010','010101','101010','010101','101010','010101'],square:['1111','1111','1111','1111']};
let paint=null;
$('shapeGrid').addEventListener('pointerdown',e=>{const b=e.target.closest('.shape-cell');if(!b)return;e.preventDefault();paint=state.shape[+b.dataset.y][+b.dataset.x]==='1'?'0':'1';paintCell(b);sfx('zoom');});
$('shapeGrid').addEventListener('pointerover',e=>{if(paint!==null&&e.buttons){const b=e.target.closest('.shape-cell');if(b)paintCell(b);}});
$('shapeGrid').addEventListener('click',e=>{if(e.detail===0){const b=e.target.closest('.shape-cell');if(b){paint=state.shape[+b.dataset.y][+b.dataset.x]==='1'?'0':'1';paintCell(b);paint=null;}}});
function paintCell(b){state.shape[+b.dataset.y][+b.dataset.x]=paint;b.classList.toggle('on',paint==='1');b.setAttribute('aria-pressed',paint==='1');updateProbability();}
window.addEventListener('pointerup',()=>{paint=null;});
document.querySelectorAll('[data-pattern]').forEach(b=>b.onclick=()=>{const pattern=patterns[b.dataset.pattern];const n=Math.max(state.shapeSize,pattern.length,pattern[0].length);$('shapeSize').value=String([4,5,6,8,12,16].find(s=>s>=n)||16);buildShape(+$('shapeSize').value,pattern);sfx();});
$('clearShape').onclick=()=>{buildShape(state.shapeSize);sfx();};$('shapeSize').onchange=()=>buildShape(+$('shapeSize').value);
$('cropShape').onchange=updateProbability;$('sweepWidth').onchange=()=>{$('sweepRange').hidden=!$('sweepWidth').checked;};
$('imageInput').onchange=async e=>{
 const file=e.target.files[0];if(!file)return;try{const bitmap=await createImageBitmap(file),n=state.shapeSize;const c=document.createElement('canvas');c.width=c.height=n;const context=c.getContext('2d');context.fillStyle='white';context.fillRect(0,0,n,n);const ratio=Math.min(n/bitmap.width,n/bitmap.height);context.drawImage(bitmap,(n-bitmap.width*ratio)/2,(n-bitmap.height*ratio)/2,bitmap.width*ratio,bitmap.height*ratio);const pixels=context.getImageData(0,0,n,n).data;const rows=Array.from({length:n},(_,y)=>Array.from({length:n},(_,x)=>{const i=(y*n+x)*4;return(pixels[i]*.2126+pixels[i+1]*.7152+pixels[i+2]*.0722)<128?'1':'0';}).join(''));buildShape(n,rows);toast('Image reduced to '+n+' × '+n+' pixels. White cells represent dark image areas.');}catch(e){toast(e.message);}e.target.value='';
};
async function search(){
 if(state.job)return;
 const mode=state.searchMode;
 try{
  if(!state.count)throw Error('Compute some digits first.');
  let payload={mode,scheme:state.scheme,rule:state.rule,alignment:state.alignment,query:$('queryInput').value.trim(),width:state.cols};
  if(mode==='shape'){payload.rows=getShape();payload.sweep=$('sweepWidth').checked;payload.minWidth=+$('minWidth').value;payload.maxWidth=+$('maxWidth').value;state.shapeRows=payload.rows;}
  else if(!payload.query)throw Error('Enter a search pattern.');
  setView(mode==='shape'?'binary':mode,false);sfx('compute');
  $('generateSection').classList.add('collapsed');$('toggleGenerate').setAttribute('aria-expanded','false');
  $('sidebar').scrollTo({top:0,behavior:'smooth'});
  $('searchBtn').disabled=true;$('searchOverlay').hidden=false;$('searchMessage').textContent='Preparing '+(mode==='shape'?'native pixel search…':'search…');
  const result=await api('search',payload);state.job=result.id;
  let job;
  do{job=await api('job/'+state.job);$('searchMessage').textContent=job.message+(job.progress>0&&job.progress<1?' · '+Math.round(job.progress*100)+'%':'');if(job.status==='running')await new Promise(r=>setTimeout(r,65));}while(job.status==='running');
  if(job.status==='error')throw Error(job.error);if(job.status==='cancelled'){toast('Search cancelled.');return;}
  state.matches=job.matches;state.active=-1;state.query=job.query;
  state.history.unshift({mode,query:mode==='shape'?'Pixel pattern':payload.query,count:job.matches.length,date:new Date().toISOString()});state.history=state.history.slice(0,20);savePrefs();
  renderResults(job);if(job.matches.length){sfx('found');selectMatch(0);}else{sfx('empty');invalidate();}
 }catch(e){toast(e.message);}finally{state.job=null;$('searchBtn').disabled=false;$('searchOverlay').hidden=true;}
}
function renderResults(job){
 $('resultHeading').textContent=state.searchMode==='shape'?'PATTERNS FOUND':'MATCHES FOUND';$('resultCount').textContent=fmt(job.matches.length)+(job.capped?'+':'');
 const el=$('results');el.innerHTML='';
 const summary=document.createElement('p');summary.className='result-summary';summary.textContent=job.matches.length?`${job.capped?'First ':''}${fmt(job.matches.length)} matches · ${job.seconds.toFixed(3)}s\n${job.capped?'Search range: ':''}${fmt(job.scanned)} ${state.searchMode==='text'?'characters':'digits'}${job.capped?' · stopped at result limit':' searched'}`:`No matches in ${fmt(job.scanned)} ${state.searchMode==='text'?'characters':'digits'}. Try a shorter pattern, more digits, or a wider sweep.`;el.append(summary);
 if(job.scan){const info=document.createElement('p');info.className='result-summary';info.textContent=job.scan.cacheHit?'Exact result reused · '+job.seconds.toFixed(4)+'s':job.scan.backend+(job.scan.threads?' · '+job.scan.threads+' threads':'')+(job.digitsPerSecond?'\n'+(job.digitsPerSecond/1e9).toFixed(2)+' billion source digits/s':'');el.append(info);}
 job.matches.forEach((match,i)=>{const b=document.createElement('button');b.className='result-card';b.innerHTML=`<div class="result-top"><strong></strong><small>↗</small></div><p></p>`;b.querySelector('strong').textContent='# '+fmt(match.position);b.querySelector('p').textContent=state.searchMode==='shape'?`Row width ${match.width} · ${match.shapeWidth} × ${match.height} pixels`:state.searchMode==='text'?`Character ${fmt(match.unitPosition)} · decimal digit ${fmt(match.position)}`:`Match ${i+1} · ${match.length} digits`;b.onclick=()=>{selectMatch(i);sfx();};el.append(b);});
}
function selectMatch(i){
 state.active=i;const match=state.matches[i];if(!match)return;
 if(match.width){state.cols=match.width;$('rowWidth').value=match.width;setView('binary',false);}
 document.querySelectorAll('.result-card').forEach((b,j)=>b.classList.toggle('active',j===i));
 $('canvasTitle').textContent=state.searchMode==='shape'?'Hidden in plain sight.':'There it is.';
 $('canvasSubtitle').textContent=state.searchMode==='text'?`“${state.query}” · character ${fmt(match.unitPosition)} · digit ${fmt(match.position)}`:state.searchMode==='shape'?`${match.shapeWidth} × ${match.height} pixels · width ${match.width} · digit ${fmt(match.position)}`:`“${state.query}” begins at decimal place ${fmt(match.position)}.`;
 flyTo(digitToUnits(match.position-1),match.width?Math.min(5,Math.max(3.5,(W-160)/(Math.min(match.width,70)*12))):undefined,match.shapeWidth||match.length||1,match.height||1);
}
$('searchBtn').onclick=search;$('queryInput').onkeydown=e=>{if(e.key==='Enter')search();};$('queryInput').oninput=updateProbability;
$('cancelSearch').onclick=()=>{if(state.job)api('search/cancel',{id:state.job}).catch(e=>toast(e.message));};
async function calculate(){
 try{
  clearTimeout(statusTimer);statusTimer=null;if(statusPollPromise)await statusPollPromise;clearTimeout(statusTimer);statusTimer=null;
  if(state.computing){await api('cancel',{});toast('Stopping computation…');return;}
  const count=readComputeCount();
  if(targetConstant()!=='pi'&&!state.constantsSupported)throw Error('Restart Pi Explorer to load the multi-constant engine.');
  await api('compute',{count,constant:targetConstant(),method:$('engineSelect').value,force:$('forceCompute').checked,storageMode:$('memoryMode').value});state.computing=true;state.requestedCount=count;sfx('compute');await pollStatus();
 }catch(e){toast(e.message);}finally{if(!statusTimer&&!statusPollPromise)void pollStatus();}
}
let statusTimer=null,statusPollPromise=null;
function pollStatus(initial=false){
 if(state.shuttingDown)return Promise.resolve();
 if(statusPollPromise)return statusPollPromise;
 clearTimeout(statusTimer);statusTimer=null;
 statusPollPromise=readStatus(initial).finally(()=>{statusPollPromise=null;if(!state.shuttingDown)statusTimer=setTimeout(()=>pollStatus(),state.computing?200:1500);});
 return statusPollPromise;
}
async function readStatus(initial=false){
 if(state.shuttingDown)return;
 try{
  const status=await api('status');state.token=status.token;state.maxDigits=status.maxDigits;const wasBusy=state.computing;state.computing=status.busy;state.constantsSupported=Array.isArray(status.constants);
  if(initial&&status.constant){$('constantSelect').value=status.busy?(status.targetConstant||status.constant):status.constant;syncNumberOptions();}
  $('generateSection').classList.toggle('computing',status.busy);
  for(const id of ['digitCount','constantSelect','engineSelect','memoryMode','forceCompute'])$(id).disabled=status.busy||(id==='memoryMode'&&$('engineSelect').value==='compact');
  $('computeBtn').disabled=!status.busy&&!!state.planBlocked;
  document.querySelectorAll('[data-count]').forEach(button=>button.disabled=status.busy);
  if(status.busy&&status.target)$('digitCount').value=status.target;
  $('footerStatus').textContent=window.PiLocalApi?'STANDALONE HTML · ALL DATA STAYS IN YOUR BROWSER':'COMPUTED LOCALLY · EXPLORED ENDLESSLY';
  $('computeBtn').classList.toggle('computing',status.busy);$('computeBtn').querySelector('span').textContent=status.busy?'Cancel computation':'Calculate '+NUMBERS[targetConstant()].symbol;
  $('computeMessage').textContent=status.error||status.message;$('computeProgress').style.width=(status.progress*100)+'%';$('computeTime').textContent=status.busy&&status.elapsed!==undefined?computeLive.duration(status.elapsed):status.cacheHit?'cache · '+(status.operationSeconds*1000).toFixed(1)+'ms':status.seconds?computeLive.duration(status.seconds):'—';
  computeLive.update(status);
  $('engineLabel').textContent=status.busy?status.telemetry?'COMPUTING · '+status.telemetry.phaseLabel.toUpperCase():'COMPUTING · '+Math.round(status.progress*100)+'% ESTIMATE':window.PiLocalApi?'BROWSER PRECISION ENGINE':'NATIVE PRECISION ENGINE';
  if(status.busy&&status.resourcePlan?.mode){$('resourcePlan').textContent=resourceText(status.resourcePlan);$('resourcePlan').classList.remove('error');}
  if(status.error&&wasBusy)toast(status.error.slice(-200));
  if(status.count!==state.count||(status.datasetId!==undefined&&status.datasetId!==state.datasetId)||(wasBusy&&!status.busy&&!status.cancelled&&!status.error)){
   state.datasetId=status.datasetId;state.constant=status.constant||'pi';
   const number=NUMBERS[state.constant];$('integerPart').textContent=number.integer+'.';$('searchBtn').querySelector('span').textContent='Search in '+number.symbol;$('exportBtn').textContent='↧ Export '+number.symbol;$('constantFooter').textContent=number.symbol+' IS IRRATIONAL. YOUR CURIOSITY ISN’T.';
   state.count=status.count;state.chunkKey='';state.chunk='';cache.clear();state.stats=null;
   state.matches=[];state.active=-1;renderNotebook();
   $('loadedCount').textContent=fmt(state.count);$('navEnd').textContent=fmt(state.count);$('canvasEmpty').hidden=state.count>0;
   $('loadedMethod').textContent=status.method==='tachuspi'?'TachusPI / packed':status.method==='ycruncher-low'?'y-cruncher / packed':status.method==='compact'?'Compact exact / MPFR verified':status.method==='exact'?'Exact GMP / certified':status.method==='chudnovsky'?'Chudnovsky / GMP':status.method==='mpfr'?'Native MPFR':status.method==='ycruncher'?'y-cruncher / CPU':status.method==='browser'?'Chudnovsky / browser':status.method==='bundled'?'Verified bundled digits':'Imported digits';
   $('canvasTitle').textContent='Look closer.';$('loadedMethod').textContent=number.symbol+' · '+$('loadedMethod').textContent;
   $('canvasSubtitle').textContent=number.symbol+' · '+fmt(state.count)+' digits. Countless possibilities.';
   if(!initial&&wasBusy){state.matches=[];state.active=-1;toast(fmt(state.count)+' decimal places ready.');sfx('found');}
   fit(true);invalidate();
  }
  if(initial){$('digitCount').value=status.busy&&status.target?status.target:Math.min(computeLimit(),state.count||5000000);if(!state.count)$('canvasEmpty').hidden=false;}
  if(initial||(wasBusy&&!status.busy))void refreshPlan();
 }catch(e){if(state.lastStatusError!==e.message){console.warn('Status refresh: '+e.message);state.lastStatusError=e.message;}if(!state.shuttingDown)$('footerStatus').textContent='LOCAL ENGINE UNAVAILABLE · REOPEN START PI EXPLORER';}
}
$('computeBtn').onclick=calculate;$('emptyCompute').onclick=()=>{$('digitCount').value=Math.min(5000000,computeLimit());calculate();};
$('toggleGenerate').onclick=()=>{const collapsed=$('generateSection').classList.toggle('collapsed');$('toggleGenerate').setAttribute('aria-expanded',String(!collapsed));};
document.querySelectorAll('[data-count]').forEach(b=>b.onclick=()=>{$('digitCount').value=b.dataset.count;document.querySelectorAll('[data-count]').forEach(x=>x.classList.toggle('active',x===b));void refreshPlan();sfx();});
$('constantSelect').onchange=()=>{syncNumberOptions();$('computeBtn').querySelector('span').textContent='Calculate '+NUMBERS[targetConstant()].symbol;engineChanged();};
$('digitCount').oninput=()=>{clearTimeout(planTimer);planTimer=setTimeout(refreshPlan,200);};$('engineSelect').onchange=engineChanged;$('memoryMode').onchange=refreshPlan;$('forceCompute').onchange=refreshPlan;
$('compactCheckBtn').onclick=checkCompactTarget;
$('compactAutoBtn').onclick=useRamAwareAuto;
document.querySelectorAll('[data-search]').forEach(b=>b.onclick=()=>setSearchMode(b.dataset.search));
document.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{setView(b.dataset.view);sfx();});
$('rowWidth').onchange=()=>{const v=+$('rowWidth').value;if(!Number.isInteger(v)||v<4||v>4096){$('rowWidth').value=state.cols;toast('Row width must be 4–4,096.');return;}state.cols=v;state.active=-1;fit();sfx();};
$('textScheme').onchange=()=>{state.scheme=$('textScheme').value;state.matches=[];state.active=-1;state.chunkKey='';updateProbability();setView('text');};
$('pairOffset').onchange=()=>{state.alignment=$('pairOffset').checked?1:0;state.chunkKey='';state.matches=[];state.active=-1;invalidate();};
$('pixelRule').value=state.rule;$('pixelRule').onchange=()=>{state.rule=$('pixelRule').value;state.matches=[];state.active=-1;state.chunkKey='';savePrefs();if(state.view==='binary')setView('binary',false);};
canvas.addEventListener('wheel',e=>{e.preventDefault();const r=canvas.getBoundingClientRect();if(e.shiftKey){state.ty-=e.deltaY;state.tx-=e.deltaX;clampCamera();invalidate();}else zoom(Math.exp(-e.deltaY*.0015),e.clientX-r.left,e.clientY-r.top);},{passive:false});
canvas.addEventListener('pointerdown',e=>{if(e.button!==0&&e.button!==1)return;canvas.setPointerCapture(e.pointerId);drag={x:e.clientX,y:e.clientY,tx:state.tx,ty:state.ty};pointerMoved=false;$('hoverCard').hidden=true;});
canvas.addEventListener('pointermove',e=>{if(!drag)return;const dx=e.clientX-drag.x,dy=e.clientY-drag.y;pointerMoved||=Math.abs(dx)+Math.abs(dy)>3;state.tx=drag.tx+dx;state.ty=drag.ty+dy;clampCamera();invalidate();});
canvas.addEventListener('pointerup',e=>{drag=null;if(canvas.hasPointerCapture(e.pointerId))canvas.releasePointerCapture(e.pointerId);});
canvas.addEventListener('pointercancel',()=>{drag=null;});
canvas.addEventListener('dblclick',async e=>{
 const r=canvas.getBoundingClientRect(),{cw,ch}=geometry(),x=e.clientX-r.left,y=e.clientY-r.top;const col=Math.floor((x-state.tx)/(cw*state.scale)),row=Math.floor((y-state.ty)/(ch*state.scale));
 const index=row*state.cols+col;if(row<0||col<0||col>=state.cols||index>=totalUnits())return;
 const digit=unitsToDigit(index),card=$('hoverCard');const v=viewport.charAt(index,dataKey())||(await api('digits?'+new URLSearchParams({start:index,count:1,mode:state.view,scheme:state.scheme,rule:state.rule,alignment:state.alignment}))).data;
 card.innerHTML='<b></b><br><span></span><br><small></small>';card.querySelector('b').textContent=v;card.querySelector('span').textContent='Decimal place '+fmt(digit+1);card.querySelector('small').textContent='Row '+fmt(row+1)+' · column '+fmt(col+1);card.style.left=Math.min(W-210,Math.max(10,x+13))+'px';card.style.top=Math.min(H-110,Math.max(10,y-90))+'px';card.hidden=false;sfx();
});
$('zoomIn').onclick=()=>{zoom(1.4);sfx('zoom');};$('zoomOut').onclick=()=>{zoom(1/1.4);sfx('zoom');};$('zoomReset').onclick=()=>fit(false);$('goHome').onclick=()=>{fit(true);sfx();};
let sliderTimer;$('positionSlider').oninput=()=>{clearTimeout(sliderTimer);sliderTimer=setTimeout(()=>{const digit=Math.floor((state.count-1)*+$('positionSlider').value/1000000);const index=digitToUnits(digit),{ch}=geometry();state.ty=H*.32-Math.floor(index/state.cols)*ch*state.scale;clampCamera();invalidate();},25);};
function jump(){const n=Number($('jumpInput').value.replace(/[,\s]/g,''));if(!Number.isSafeInteger(n)||n<1||n>state.count){toast('Enter a decimal place from 1 to '+fmt(state.count)+'.');return;}flyTo(digitToUnits(n-1));sfx();}
$('jumpBtn').onclick=jump;$('jumpInput').onkeydown=e=>{if(e.key==='Enter')jump();};
function toggleFocus(){document.body.classList.toggle('focus-mode');resize();}
$('focusBtn').onclick=()=>{toggleFocus();sfx();};$('soundBtn').classList.toggle('muted',!state.sound);$('soundBtn').onclick=()=>{state.sound=!state.sound;$('soundBtn').classList.toggle('muted',!state.sound);$('soundBtn').setAttribute('aria-pressed',state.sound);savePrefs();if(state.sound)sfx('found');toast('Sound effects '+(state.sound?'enabled':'muted'));};
$('volume').value=state.volume*100;$('volume').oninput=()=>{state.volume=+$('volume').value/100;savePrefs();};$('volume').onchange=()=>sfx();
$('helpBtn').onclick=()=>{$('guideDialog').showModal();sfx();};document.querySelectorAll('.dialog-close').forEach(b=>b.onclick=()=>b.closest('dialog').close());
document.querySelectorAll('dialog').forEach(d=>d.addEventListener('click',e=>{if(e.target===d){const r=d.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)d.close();}}));
$('statsBtn').onclick=async()=>{
 $('statsDialog').showModal();$('statsContent').textContent='Analyzing '+fmt(state.count)+' digits…';sfx();
 try{const stats=state.stats||await api('stats');state.stats=stats;const el=$('statsContent');el.innerHTML='';const max=Math.max(...stats.counts,1);
  stats.counts.forEach((count,digit)=>{const row=document.createElement('div');row.className='stat-row';row.innerHTML=`<span>${digit}</span><div class="stat-track"><i style="background:${palette[digit]};width:${count/max*100}%"></i></div><span>${fmt(count)} · ${(count/(stats.count||1)*100).toFixed(3)}%</span>`;el.append(row);});
  const facts=document.createElement('div');facts.className='stat-facts';facts.innerHTML=`<p>SHANNON ENTROPY<b>${stats.entropy.toFixed(6)}</b>bits / digit · max 3.321928</p><p>LONGEST IDENTICAL RUN<b>${stats.longestRun.length} × ${stats.longestRun.digit}</b>at decimal place ${fmt(stats.longestRun.position)}</p><p>CHI-SQUARE<b>${stats.chiSquare.toFixed(3)}</b>10 categories · 9 degrees of freedom</p><p>DECIMAL PLACES<b>${fmt(stats.count)}</b>Excludes the integer part, ${NUMBERS[state.constant].integer}.</p>`;el.append(facts);const hash=document.createElement('p');hash.className='hash';hash.textContent='DIGIT FILE SHA-256 / '+stats.sha256;el.append(hash);
 }catch(e){$('statsContent').textContent=e.message;}
};
function download(blob,name){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
$('captureBtn').onclick=()=>{canvas.toBlob(blob=>{if(blob)download(blob,'pi-explorer-'+state.view+'-'+Date.now()+'.png');},'image/png');sfx('bookmark');toast('Canvas saved as PNG.');};
$('bookmarkBtn').onclick=()=>{
 const {ch}=geometry();const index=Math.max(0,Math.floor((H*.4-state.ty)/(ch*state.scale))*state.cols);const b={constant:state.constant,view:state.view,digit:Math.min(state.count-1,unitsToDigit(index)),cols:state.cols,scale:state.scale,scheme:state.scheme,alignment:state.alignment,rule:state.rule};state.bookmarks.unshift(b);state.bookmarks=state.bookmarks.slice(0,20);savePrefs();sfx('bookmark');toast('View bookmarked at digit '+fmt(b.digit+1)+'.');renderNotebook();
};
function renderNotebook(){
 if(state.matches.length)return;
 const el=$('results');el.innerHTML='';$('resultHeading').textContent='SAVED VIEWS';$('resultCount').textContent=String(state.bookmarks.length).padStart(2,'0');
 if(!state.bookmarks.length){el.innerHTML='<div class="empty-results"><div class="orbit-icon">⌕</div><p>What are you looking for?</p><span>Your next discovery is a search away.</span></div>';return;}
 state.bookmarks.forEach(b=>{const button=document.createElement('button');button.className='result-card';button.innerHTML='<div class="result-top"><strong></strong><small>⌑</small></div><p></p>';button.querySelector('strong').textContent='Digit '+fmt(b.digit+1);button.querySelector('p').textContent=NUMBERS[b.constant||'pi'].symbol+' · '+b.view.toUpperCase()+' · width '+b.cols;button.onclick=()=>{if((b.constant||'pi')!==state.constant){toast('This bookmark belongs to '+NUMBERS[b.constant||'pi'].symbol+'. Load that constant first.');return;}if(b.digit>=state.count){toast('Compute more digits to open this bookmark.');return;}state.cols=b.cols;state.scheme=b.scheme;state.alignment=b.alignment||0;state.rule=b.rule||'threshold';$('rowWidth').value=b.cols;$('textScheme').value=state.scheme;$('pairOffset').checked=state.alignment===1;$('pixelRule').value=state.rule;setView(b.view,false);flyTo(digitToUnits(b.digit),b.scale);sfx();};el.append(button);});
}
$('importBtn').onclick=()=>$('importInput').click();$('importInput').onchange=async e=>{const file=e.target.files[0];if(!file)return;try{if(!window.PiLocalApi){const available=await api('status');if(file.size>available.maxInlineImportBytes)throw Error('This file exceeds the current RAM budget for inline import. Place pi-<count>.txt in the app data folder and reopen to load it without copying.');}toast('Reading digit file…');const result=await api('import',{constant:targetConstant(),digits:await file.text()});await pollStatus();toast(fmt(result.count)+' digits imported. Prefix checked; remainder supplied by your file.');}catch(e){toast(e.message);}e.target.value='';};
$('exportBtn').onclick=async()=>{if(!state.count){toast('Compute digits first.');return;}try{if(window.PiLocalApi)download(new Blob([await api('export')],{type:'text/plain'}),state.constant+'-'+state.count+'-decimal-places.txt');else{const a=document.createElement('a');a.href='/api/export';a.download=state.constant+'-'+state.count+'-decimal-places.txt';a.click();}sfx();}catch(e){toast(e.message);}};
$('quitBtn').onclick=async()=>{try{if(state.job)await api('search/cancel',{id:state.job});state.shuttingDown=true;await api('shutdown',{});$('guideDialog').close();toast('Local engine stopped. Close this window; use Start Pi Explorer to reopen.');$('footerStatus').textContent='LOCAL ENGINE STOPPED';}catch(e){toast(e.message);}};
document.addEventListener('keydown',e=>{
 if(/INPUT|SELECT|TEXTAREA/.test(e.target.tagName)||document.querySelector('dialog[open]'))return;
 if(e.key==='f'||e.key==='F'){e.preventDefault();toggleFocus();}else if(e.key==='0'){e.preventDefault();fit(false);}else if(e.key==='Home'){e.preventDefault();fit(true);}else if(e.key==='Escape'){$('hoverCard').hidden=true;if(document.body.classList.contains('focus-mode'))toggleFocus();}else if(e.key==='+'||e.key==='=')zoom(1.3);else if(e.key==='-')zoom(1/1.3);else if(e.key==='ArrowDown'){e.preventDefault();state.ty-=120;clampCamera();invalidate();}else if(e.key==='ArrowUp'){e.preventDefault();state.ty+=120;clampCamera();invalidate();}else if(e.key==='Enter')search();
});
document.addEventListener('pointerdown',e=>{if(!e.target.closest('#piCanvas'))$('hoverCard').hidden=true;});
$('paletteLegend').innerHTML=palette.map((c,i)=>`<span><i style="background:${c}"></i>${i}</span>`).join('');
buildShape(6,patterns.pi);renderNotebook();resize();
document.fonts.ready.then(()=>invalidate());
pollStatus(true).then(()=>fit(true)).finally(()=>{$('computeBtn').disabled=false;$('searchBtn').disabled=false;});
