"""Bounded-memory searches over memory-mapped digit stores."""
import time
import numpy as np
import engine
from digit_store import unit_step
import fast_search

def _inverse_query(query,mode,scheme):
    if mode in ('digits','colors'):return query
    if mode!='text':return None
    if scheme=='a1z26' and all(65<=v<=90 for v in query):
        return b''.join(f'{v-64:02d}'.encode() for v in query)
    if scheme=='ascii' and all(32<=v<=126 and v!=46 for v in query):
        return b''.join(f'{v:03d}'.encode() for v in query)
    return None


def _mapped_sequence(store,query,raw,mode,scheme,alignment,limit,cancelled,progress,metrics):
    step=unit_step(mode,scheme);alignment=alignment if mode=='text' else 0
    total=store.total_units(mode,scheme,alignment);candidates=max(0,total-len(query)+1)
    matches=[];chunk=max(1,16*1024*1024//step)
    for begin in range(0,candidates,chunk):
        if cancelled():raise InterruptedError('Search cancelled')
        end=min(candidates,begin+chunk)
        start=alignment+begin*step;stop=alignment+(end-1)*step+len(raw)
        while True:
            at=store.find(raw,start,stop)
            if at<0:break
            if (at-alignment)%step==0:
                matches.append((at-alignment)//step)
                if len(matches)>limit:
                    if metrics is not None:metrics.update(backend='Zero-copy mapped search',scanned=matches[-1]+len(query),sourceDigits=at+len(raw),cacheHit=False,threads=1)
                    return matches[:limit],True,0
            start=at+1
            if cancelled():raise InterruptedError('Search cancelled')
        if progress:progress(end/max(1,candidates),f'Searched {end:,} of {total:,} units without decoding')
    if metrics is not None:metrics.update(backend='Zero-copy mapped search',scanned=total,sourceDigits=len(store),cacheHit=False,threads=1)
    return matches,False,0


def search_sequence(store,query,mode='digits',scheme='mod26',alignment=0,limit=300,cancelled=lambda:False,progress=None,metrics=None):
    if cancelled():raise InterruptedError('Search cancelled')
    if not query:raise ValueError('Enter a nonempty pattern')
    if limit<1:raise ValueError('Result limit must be positive')
    if mode=='text' and scheme not in ('mod26','a1z26','ascii'):raise ValueError('Unknown text encoding')
    if mode=='text' and not 0<=alignment<unit_step(mode,scheme):raise ValueError('Invalid text alignment')
    if fast_search.available() and hasattr(store,'mapping') and not getattr(store,'packed',False):
        return fast_search.sequence(store,query,mode,scheme,alignment,limit,cancelled,progress,metrics)
    # The same bounded result cache now also accelerates source-only and packed searches.
    key=(fast_search._identity(store),'portable-sequence',bytes(query),mode,scheme,alignment,limit)
    cached=fast_search._get(key)
    if cached is not None:
        positions,capped,details=cached
        if metrics is not None:metrics.update(details,backend='Exact result cache',cacheHit=True,threads=0)
        if progress:progress(1,'Loaded exact search results for this unchanged dataset')
        return list(positions),capped,0
    details={};raw=_inverse_query(query,mode,scheme)
    if raw is not None and hasattr(store,'find') and not getattr(store,'packed',False):
        result=_mapped_sequence(store,query,raw,mode,scheme,alignment,limit,cancelled,progress,details)
    else:result=_stream_sequence(store,query,mode,scheme,alignment,limit,cancelled,progress,details)
    if cancelled():raise InterruptedError('Search cancelled')
    fast_search._put(key,(tuple(result[0]),result[1],dict(details)))
    if metrics is not None:metrics.update(details)
    return result


def _stream_sequence(store,query,mode='digits',scheme='mod26',alignment=0,limit=300,cancelled=lambda:False,progress=None,metrics=None):
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
