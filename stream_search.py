"""Bounded-memory searches over memory-mapped digit stores."""
import time
import numpy as np
import engine
from digit_store import unit_step
import fast_search

def search_sequence(store,query,mode='digits',scheme='mod26',alignment=0,limit=300,cancelled=lambda:False,progress=None,metrics=None):
    if fast_search.available() and hasattr(store,'mapping') and not getattr(store,'packed',False):
        return fast_search.sequence(store,query,mode,scheme,alignment,limit,cancelled,progress,metrics)
    step=unit_step(mode,scheme);total=store.total_units(mode,scheme,alignment);chunk_units=2*1024*1024
    matches=[];tail=b'';conversion_seconds=0
    for cursor in range(0,total,chunk_units):
        if cancelled():raise InterruptedError('Search cancelled')
        started=time.perf_counter();data,_=store.window(cursor,min(chunk_units,total-cursor),mode,scheme,alignment=alignment);conversion_seconds+=time.perf_counter()-started
        combined=tail+data;start=0
        while True:
            at=combined.find(query,start)
            if at<0:break
            position=cursor-len(tail)+at
            if len(matches)>=limit:
                if metrics is not None:metrics.update(scanned=min(total,cursor+len(data)),backend='Streaming fallback',cacheHit=False)
                return matches,True,conversion_seconds
            matches.append(position);start=at+1
        tail=combined[-(len(query)-1):] if len(query)>1 else b''
        if progress:progress(min(1,(cursor+len(data))/max(total,1)),f'Scanned {min(total,cursor+len(data)):,} of {total:,} characters')
    if metrics is not None:metrics.update(scanned=total,backend='Streaming fallback',cacheHit=False)
    return matches,False,conversion_seconds

def search_shapes(store,rows,widths,rule='threshold',limit=60,cancelled=lambda:False,progress=None,metrics=None):
    if fast_search.available() and hasattr(store,'mapping') and not getattr(store,'packed',False):
        return fast_search.shapes(store,rows,widths,rule,limit,cancelled,progress,metrics)
    widths=list(widths)
    if not widths:raise ValueError('Choose a valid row-width range')
    halo=(len(rows)-1)*max(widths)+len(rows[0])-1;block=2*1024*1024;matches=[]
    for start in range(0,len(store),block):
        if cancelled():raise InterruptedError('Search cancelled')
        core=min(block,len(store)-start);raw=store[start:min(len(store),start+core+halo)]
        a=np.frombuffer(raw,dtype=np.uint8);on=((a-48)%2).astype(bool) if rule=='parity' else a>=53
        packed=np.packbits(on,bitorder='little').tobytes();bits=engine.g.mpz.from_bytes(packed,'little')
        # Only the length of the legacy bits parameter is used with source_bits.
        found,capped=engine.find_shapes(memoryview(raw),rows,widths,limit-len(matches),None,cancelled,start,core,bits)
        for match in found:match['index']+=start;match['position']+=start
        matches.extend(found)
        if capped or len(matches)>=limit:return sorted(matches,key=lambda m:(m['index'],m['width'])),True
        if progress:progress(min(1,(start+core)/len(store)),f'Searched {min(len(store),start+core):,} of {len(store):,} digits across {len(widths)} widths')
    return sorted(matches,key=lambda m:(m['index'],m['width'])),False
