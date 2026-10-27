/* Phase percentages are native measurements; no fabricated digits-per-second. */
window.PiComputeLive=class PiComputeLive{
 constructor(resolve){this.el=resolve;this.samples=[];this.job=null;this.sequence=null;}
 rate(value){if(!Number.isFinite(value))return'—';return value>=1048576?(value/1048576).toFixed(1)+' MiB/s':Math.round(value/1024)+' KiB/s';}
 duration(seconds){if(!Number.isFinite(seconds))return'—';return seconds<60?seconds.toFixed(1)+'s':Math.floor(seconds/60)+'m '+Math.floor(seconds%60)+'s';}
 update(status){
  const el=this.el,t=status.telemetry,live=Boolean(status.busy&&t),panel=el('computeLive');panel.hidden=!status.busy;
  if(!status.busy){this.job=null;this.samples=[];this.sequence=null;el('computeProgress').parentElement.classList.remove('indeterminate');return;}
  const key=status.nativeJob||status.startedAt||status.target||'browser';
  if(key!==this.job){this.job=key;this.samples=[];this.sequence=null;}
  const native=live||Boolean(status.nativeJob)||status.progressKind==='phase',known=live&&Number.isFinite(t.phaseProgress),stale=live&&(t.ageSeconds||0)>2;
  panel.classList.toggle('no-metrics',!live);
  el('liveBadge').textContent=stale?'WAITING FOR UPDATE':live?'LIVE':status.nativeJob?'WAITING':status.progress>0?'COMPUTING':'STARTING';el('liveBadge').classList.toggle('stale',stale);
  el('phasePercent').textContent=known?Math.round(t.phaseProgress*100)+'% of phase':native?'Working…':Math.round((status.progress||0)*100)+'% overall estimate';
  el('phaseDetail').textContent=live?'Phase '+t.phaseStep+' / '+t.phaseSteps+' · '+this.duration(t.phaseElapsed)+' in this phase':status.message;
  el('cpuMetric').textContent=live&&Number.isFinite(t.cpuPercent)?t.cpuPercent.toFixed(0)+'%':'—';
  el('ramMetric').textContent=live&&Number.isFinite(t.residentBytes)?Math.round(t.residentBytes/1048576).toLocaleString('en-US')+' MiB':'—';
  el('readMetric').textContent=this.rate(live?t.readBytesPerSecond:undefined);el('writeMetric').textContent=this.rate(live?t.writeBytesPerSecond:undefined);
  const track=el('computeProgress').parentElement;track.classList.toggle('indeterminate',native&&!known);
  el('computeProgress').style.width=native?(known?t.phaseProgress*100+'%':'40%'):Math.round((status.progress||0)*100)+'%';
  if(live&&Number.isFinite(t.cpuPercent)&&t.sequence!==this.sequence){
   this.sequence=t.sequence;const now=t.updatedAt;this.samples.push({at:now,cpu:t.cpuPercent});this.samples=this.samples.filter(s=>s.at>=now-45).slice(-200);
   const path=this.samples.map((s,i)=>(i?'L':'M')+Math.max(0,Math.min(220,(s.at-now+45)/45*220)).toFixed(1)+','+(34-Math.max(0,Math.min(100,s.cpu))*.30).toFixed(1)).join(' ');
   el('cpuTrace').setAttribute('d',path);
  }
 }
};
