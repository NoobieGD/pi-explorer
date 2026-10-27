/* Visible tiles, actual glyph mipmaps and smoothly blended text LODs. */
window.PiViewport=class PiViewport{
 constructor(request,invalidate){this.request=request;this.invalidate=invalidate;this.cache=new Map();this.tile=null;this.pending=false;this.wanted=null;this.failedAt=0;this.atlases=new Map();this.rasterLimit=24*1024*1024;this.colors=['ef5350','ff9e40','f6d85d','78cb70','39bba0','42b9d5','5486e8','a67ce8','e578b3','e4e7ee'].map(c=>[parseInt(c.slice(0,2),16),parseInt(c.slice(2,4),16),parseInt(c.slice(4),16)]);}
 smooth(a,b,x){const t=Math.max(0,Math.min(1,(x-a)/(b-a)));return t*t*(3-2*t);}
 levels(sx){const full=this.smooth(5,7,sx),fine=this.smooth(2.2,3.4,sx),micro=this.smooth(.8,1.5,sx);return{glyphs:full,fine:(1-full)*fine,micro:(1-full)*(1-fine)*micro,rows:(1-full)*(1-fine)*(1-micro)};}
 detail(sx,mode){if(mode==='colors')return'COLOR CELLS';if(mode==='binary')return'PIXEL CELLS';const a=this.levels(sx);return Object.entries(a).sort((x,y)=>y[1]-x[1])[0][0].replace('glyphs','full glyphs').replace('fine','fine glyphs').replace('micro','microglyphs').replace('rows','row overview').toUpperCase();}
 descriptor(s,W,H,cw,ch,key){
  const sx=cw*s.scale,sy=ch*s.scale,total=s.view==='text'?Math.max(0,Math.floor((s.count-s.alignment)/(s.scheme==='ascii'?3:2))):s.count;
  const pixel=s.view==='colors'||s.view==='binary';
  let rs=Math.max(1,Math.ceil((pixel?1:.8)/sy)),cs=Math.max(1,Math.ceil((pixel?1:.8)/sx));
  const first=Math.max(0,Math.floor(-s.ty/sy)-2),last=Math.min(Math.ceil(total/s.cols),Math.ceil((H-s.ty)/sy)+2),left=Math.max(0,Math.floor(-s.tx/sx)-2),right=Math.min(s.cols,Math.ceil((W-s.tx)/sx)+2);
  if(last<=first||right<=left)return null;
  const budget=pixel?450000:sx>2.2&&sx<7?100000:300000;
  const samples=Math.ceil((last-first)/rs)*Math.ceil((right-left)/cs);if(samples>budget){const f=Math.ceil(Math.sqrt(samples/budget));rs*=f;cs*=f;}
  const r0=Math.floor(first/(16*rs))*16*rs,c0=Math.floor(left/(16*cs))*16*cs;
  const rows=Math.min(2048,Math.ceil((last-r0)/rs)),cols=Math.min(4096,Math.ceil((right-c0)/cs));
  const params={gridWidth:s.cols,rowStart:r0,colStart:c0,rows,cols,rowStep:rs,colStep:cs,mode:s.view,scheme:s.scheme,rule:s.rule,alignment:s.alignment};
  return{params,dataKey:key,key:key+':'+Object.values(params).join(':'),view:s.view,gridWidth:s.cols};
 }
 trim(){let bytes=0;for(const t of this.cache.values())bytes+=t.data.length*2+[...(t.rasters?.values()||[])].reduce((sum,c)=>sum+c.width*c.height*4,0);for(const [key,t] of this.cache){if(this.cache.size<=8&&bytes<=this.rasterLimit)break;if(t===this.tile)continue;bytes-=t.data.length*2+[...(t.rasters?.values()||[])].reduce((sum,c)=>sum+c.width*c.height*4,0);this.cache.delete(key);}}
 resetGlyphs(){this.atlases.clear();for(const t of this.cache.values())t.rasters?.clear();this.invalidate();}
 ensure(d){
  if(!d)return;this.wanted=d;if(this.tile?.key===d.key)return;
  if(this.cache.has(d.key)){this.tile=this.cache.get(d.key);this.invalidate();return;}
  if(this.pending||performance.now()-this.failedAt<1500)return;
  this.pending=true;
  this.request('tile?'+new URLSearchParams(d.params)).then(data=>{
   const tile={...d,...data,rasters:new Map()};this.cache.set(d.key,tile);
   if(this.wanted?.dataKey===d.dataKey)this.tile=tile;this.trim();this.invalidate();
  }).catch(error=>{this.failedAt=performance.now();console.warn(error.message);}).finally(()=>{this.pending=false;if(this.wanted?.key!==d.key)this.ensure(this.wanted);});
 }
 atlas(width,height){
  const key=width+':'+height;if(this.atlases.has(key))return this.atlases.get(key);
  const big=document.createElement('canvas');big.width=52;big.height=88;const b=big.getContext('2d');
  b.font='56px JetBrains,Consolas,monospace';b.textAlign='center';b.textBaseline='middle';b.fillStyle='#fff';
  const small=document.createElement('canvas');small.width=width;small.height=height;const g=small.getContext('2d',{willReadFrequently:true});g.imageSmoothingEnabled=true;g.imageSmoothingQuality='high';
  const alpha=new Uint8Array(128*width*height),ink=new Float32Array(128);
  for(let code=33;code<127;code++){b.clearRect(0,0,52,88);b.fillText(String.fromCharCode(code),26,44);g.clearRect(0,0,width,height);g.drawImage(big,0,0,width,height);const p=g.getImageData(0,0,width,height).data;let sum=0;for(let i=0;i<width*height;i++){alpha[code*width*height+i]=p[i*4+3];sum+=p[i*4+3];}ink[code]=sum/(255*width*height);}
  const result={alpha,ink,width,height};this.atlases.set(key,result);return result;
 }
 raster(t,level='cells'){
  t.rasters ||=new Map();if(t.rasters.has(level))return t.rasters.get(level);
  const glyph=level==='fine'||level==='micro',a=glyph?this.atlas(level==='fine'?4:2,level==='fine'?7:4):null;
  const cw=a?.width||1,ch=a?.height||(level==='rows'?2:1),c=document.createElement('canvas');c.width=level==='rows'?1:t.cols*cw;c.height=t.rows*ch;
  const g=c.getContext('2d'),im=g.createImageData(c.width,c.height),out=im.data;
  const color=t.view==='text'?[156,174,196]:[167,175,189];
  if(level==='rows'){
   const ink=this.atlas(2,4).ink;for(let r=0;r<t.rows;r++){let sum=0,n=0;for(let col=0;col<t.cols;col++){const code=t.data.charCodeAt(r*t.cols+col);if(code!==32){sum+=ink[code]||0;n++;}}const p=r*8;if(n){out[p]=color[0];out[p+1]=color[1];out[p+2]=color[2];out[p+3]=Math.round(24+200*sum/n);}}
  }else if(glyph){
   for(let r=0;r<t.rows;r++)for(let col=0;col<t.cols;col++){const code=t.data.charCodeAt(r*t.cols+col);if(code===32)continue;const at=(code<128?code:46)*cw*ch;for(let gy=0;gy<ch;gy++)for(let gx=0;gx<cw;gx++){const alpha=a.alpha[at+gy*cw+gx];if(!alpha)continue;const p=((r*ch+gy)*c.width+col*cw+gx)*4;out[p]=color[0];out[p+1]=color[1];out[p+2]=color[2];out[p+3]=alpha;}}
  }else{
   for(let i=0;i<t.data.length;i++){const code=t.data.charCodeAt(i);if(code===32)continue;const rgb=t.view==='colors'?this.colors[code-48]||[8,10,16]:code===49?[222,223,220]:[9,11,18];const p=i*4;out[p]=rgb[0];out[p+1]=rgb[1];out[p+2]=rgb[2];out[p+3]=255;}
  }
  g.putImageData(im,0,0);t.rasters.set(level,c);this.trim();return c;
 }
 drawGlyphRows(ctx,t,s,x,y,sx,sy,W,H){
  ctx.fillStyle=s.view==='text'?'#9caec4':'#a7afbd';ctx.font=(14*s.scale)+'px JetBrains,Consolas,monospace';ctx.textBaseline='middle';
  if('letterSpacing' in ctx){ctx.letterSpacing='0px';const advance=ctx.measureText('0').width;ctx.letterSpacing=(sx-advance)+'px';ctx.textAlign='left';for(let r=0;r<t.rows;r++){const yy=y+r*sy;if(yy<-sy||yy>H)continue;ctx.fillText(t.data.slice(r*t.cols,(r+1)*t.cols),x+sx/2-advance/2,yy+sy/2);}ctx.letterSpacing='0px';}
  else{ctx.textAlign='center';for(let r=0;r<t.rows;r++)for(let col=0;col<t.cols;col++){const xx=x+col*sx,yy=y+r*sy;if(xx>-sx&&xx<W&&yy>-sy&&yy<H)ctx.fillText(t.data[r*t.cols+col],xx+sx/2,yy+sy/2);}}
 }
 draw(ctx,s,W,H,cw,ch,key){
  const d=this.descriptor(s,W,H,cw,ch,key);this.ensure(d);const t=this.tile;if(!t||t.dataKey!==key||!t.data.length)return;
  const sx=cw*s.scale,sy=ch*s.scale,x=s.tx+t.colStart*sx,y=s.ty+t.rowStart*sy;
  if(s.view==='colors'||s.view==='binary'){ctx.imageSmoothingEnabled=sx<1||sy<1;ctx.drawImage(this.raster(t),x,y,t.cols*t.colStep*sx,t.rows*t.rowStep*sy);return;}
  for(const [level,weight] of Object.entries(this.levels(sx))){if(weight<.005)continue;ctx.save();ctx.globalAlpha*=weight;
   if(level==='glyphs'&&t.rowStep===1&&t.colStep===1)this.drawGlyphRows(ctx,t,s,x,y,sx,sy,W,H);
   else{ctx.imageSmoothingEnabled=true;ctx.imageSmoothingQuality='high';ctx.drawImage(this.raster(t,level==='glyphs'?'fine':level),x,y,t.cols*t.colStep*sx,t.rows*t.rowStep*sy);}
   ctx.restore();
  }
 }
 charAt(index,key){const t=this.tile;if(!t||t.dataKey!==key)return'';const row=Math.floor(index/t.gridWidth)-t.rowStart,col=index%t.gridWidth-t.colStart;if(row<0||col<0||row%t.rowStep||col%t.colStep)return'';const r=row/t.rowStep,c=col/t.colStep;return r<t.rows&&c<t.cols?t.data[r*t.cols+c]||'':'';}
};
