from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'app/app.js';s=p.read_text(encoding='utf-8')
if 'const viewport=new PiViewport' not in s:
 s=s.replace('const cache=new Map();','const cache=new Map();\nconst viewport=new PiViewport(api,invalidate);')
 start=s.index('async function ensureChunk(');end=s.index('function render()',start);s=s[:start]+s[end:]
 start=s.index(' const hasData=state.chunkKey===dataKey();');end=s.index(' drawHighlights(sx,sy);',start)
 s=s[:start]+''' viewport.draw(ctx,state,W,H,cw,ch,dataKey());
 if(sy>7){ctx.font='7px JetBrains,monospace';ctx.fillStyle='#45526a';ctx.textAlign='right';for(let row=range.first;row<range.last;row++){if(row%Math.max(1,Math.ceil(35/sy))===0)ctx.fillText(fmt(unitsToDigit(row*state.cols)+1),state.tx-12,state.ty+row*sy+sy/2);}}
'''+s[end:]
 s=s.replace('const range=visibleRange();ensureChunk(range.start,range.end);','const range=visibleRange();')
 s=s.replace("const local=p-state.chunkStart;if(state.chunkKey===dataKey()&&local>=0&&local<state.chunk.length)","const visibleChar=viewport.charAt(p,dataKey());if(visibleChar)")
 s=s.replace('ctx.fillText(state.chunk[local],px+sx/2,py+sy/2)','ctx.fillText(visibleChar,px+sx/2,py+sy/2)')
 s=s.replace("const local=index-state.chunkStart;const v=state.chunkKey===dataKey()?state.chunk[local]||'…':'…';","const v=viewport.charAt(index,dataKey())||(await api('digits?'+new URLSearchParams({start:index,count:1,mode:state.view,scheme:state.scheme,rule:state.rule,alignment:state.alignment}))).data;")
 s=s.replace("return window.PiLocalApi?.maxComputeDigits??100000000;","return window.PiLocalApi?.maxComputeDigits??state.maxDigits??1000000000;")
 s=s.replace('state.alignment,state.count].join', 'state.alignment,state.count,state.datasetId].join')
 s=s.replace("await api('compute',{count,method:$('engineSelect').value})","await api('compute',{count,method:$('engineSelect').value,force:$('forceCompute').checked})")
 s=s.replace('state.token=status.token;const wasBusy','state.token=status.token;state.maxDigits=status.maxDigits;const wasBusy')
 s=s.replace("status.seconds?status.seconds.toFixed(2)+'s':'—'","status.cacheHit?'cache · '+(status.operationSeconds*1000).toFixed(1)+'ms':status.seconds?status.seconds.toFixed(2)+'s':'—'")
 p.write_text(s,encoding='utf-8')
p=ROOT/'app/index.html';html=p.read_text(encoding='utf-8')
html=html.replace('max="100000000"','max="1000000000"')
if 'id="forceCompute"' not in html:
 html=html.replace('  <button id="computeBtn"','  <label class="check-label"><input id="forceCompute" type="checkbox"> Fresh calculation (ignore cached digits)</label>\n  <button id="computeBtn"')
 html=html.replace('<button data-count="10000000">10M</button>','<button data-count="10000000">10M</button><button data-count="100000000">100M</button><button data-count="1000000000">1B</button>')
 html=html.replace('<script src="app.js"></script>','<script src="viewport.js"></script>\n<script src="app.js"></script>')
p.write_text(html,encoding='utf-8')
print('Viewport now requests sampled visible tiles and caches raster layers.')
