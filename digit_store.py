"""Bounded-memory access to raw or native 3.<digits> pi files."""
import mmap
import os
from pathlib import Path
import numpy as np

PREFIX=b'14159265358979323846264338327950288419716939937510'
PAIR_MOD=np.array([65+i%26 for i in range(100)],dtype=np.uint8)
PAIR_A1=np.array([64+i if 1<=i<=26 else 46 for i in range(100)],dtype=np.uint8)
ASCII=np.array([i if 32<=i<=126 else 46 for i in range(1000)],dtype=np.uint8)
THRESHOLD=np.array([49 if i>=53 and i<=57 else 48 for i in range(256)],dtype=np.uint8)
PARITY=np.array([49 if 48<=i<=57 and (i-48)%2 else 48 for i in range(256)],dtype=np.uint8)

def unit_step(mode,scheme='mod26'):
    return (3 if scheme=='ascii' else 2) if mode=='text' else 1

def transform(raw,mode='digits',scheme='mod26',rule='threshold',alignment=0):
    if mode in ('digits','colors'):return bytes(raw)
    a=np.frombuffer(raw,dtype=np.uint8)
    if mode!='text':return (PARITY if rule=='parity' else THRESHOLD)[a].tobytes()
    step=unit_step(mode,scheme);n=max(0,(len(a)-alignment)//step)
    a=a[alignment:alignment+n*step]
    if scheme=='ascii':
        code=(a[::3].astype(np.uint16)-48)*100+(a[1::3].astype(np.uint16)-48)*10+(a[2::3]-48)
        return ASCII[code].tobytes()
    if scheme not in ('mod26','a1z26'):raise ValueError('Unknown text encoding')
    code=(a[::2]-48)*10+(a[1::2]-48)
    return (PAIR_A1 if scheme=='a1z26' else PAIR_MOD)[code].tobytes()

class DigitStore:
    def __new__(cls,path):
        if cls is DigitStore and Path(path).suffix.lower()=='.mpt':
            from mpt_store import MptStore
            return MptStore(path)
        if cls is DigitStore and Path(path).suffix.lower()=='.ycd':
            from ycd_store import YcdStore
            return YcdStore(path)
        return super().__new__(cls)
    def __init__(self,path):
        self.path=Path(path);self.file=self.path.open('rb')
        try:
            if self.path.stat().st_size==0:raise ValueError('Empty digit file')
            self.mapping=mmap.mmap(self.file.fileno(),0,access=mmap.ACCESS_READ)
            self.offset=2 if self.mapping[:2]==b'3.' else 0
            end=len(self.mapping)
            while end>self.offset and self.mapping[end-1] in b'\r\n \t':end-=1
            self.length=end-self.offset
            if self.length<1 or self.mapping[self.offset:self.offset+min(self.length,50)]!=PREFIX[:min(self.length,50)]:raise ValueError('Invalid pi prefix')
            self.version=f'{self.path.name}:{self.path.stat().st_mtime_ns}:{self.length}'
        except Exception:
            self.close();raise
    def __len__(self):return self.length
    def __bool__(self):return self.length>0
    def __getitem__(self,key):
        if isinstance(key,slice):
            start,end,step=key.indices(self.length)
            if step!=1:raise ValueError('Use contiguous digit windows')
            return self.mapping[self.offset+start:self.offset+end]
        if key<0:key+=self.length
        if not 0<=key<self.length:raise IndexError(key)
        return self.mapping[self.offset+key]
    def find(self,query,start=0,end=None):
        end=self.length if end is None else min(end,self.length)
        at=self.mapping.find(query,self.offset+start,self.offset+end)
        return at-self.offset if at>=0 else -1
    def chunks(self,size=4*1024*1024):
        for start in range(0,self.length,size):yield self[start:min(self.length,start+size)]
    def total_units(self,mode='digits',scheme='mod26',alignment=0):
        return max(0,(self.length-(alignment if mode=='text' else 0))//unit_step(mode,scheme))
    def window(self,start,count,mode='digits',scheme='mod26',rule='threshold',alignment=0):
        step=unit_step(mode,scheme);alignment=alignment if mode=='text' else 0
        total=self.total_units(mode,scheme,alignment);start=min(max(0,start),total);count=min(max(0,count),total-start)
        raw=self[alignment+start*step:alignment+(start+count)*step]
        return transform(raw,mode,scheme,rule),total
    def tile(self,grid_width,row_start,col_start,rows,cols,row_step=1,col_step=1,mode='digits',scheme='mod26',rule='threshold',alignment=0):
        step=unit_step(mode,scheme);alignment=alignment if mode=='text' else 0
        total=self.total_units(mode,scheme,alignment)
        out=np.full((rows,cols),32,dtype=np.uint8)
        def fill(r0,nrows,ncols):
            if nrows<=0 or ncols<=0:return
            first=(row_start+r0*row_step)*grid_width+col_start
            kw=dict(shape=(nrows,ncols),dtype=np.uint8,buffer=self.mapping,
                    strides=(row_step*grid_width*step,col_step*step))
            at=self.offset+alignment+first*step
            a=np.ndarray(offset=at,**kw)
            if mode=='text':
                b=np.ndarray(offset=at+1,**kw)
                if scheme=='ascii':
                    c=np.ndarray(offset=at+2,**kw)
                    code=(a.astype(np.uint16)-48)*100+(b.astype(np.uint16)-48)*10+(c-48);value=ASCII[code]
                else:value=(PAIR_A1 if scheme=='a1z26' else PAIR_MOD)[(a-48)*10+(b-48)]
            elif mode in ('binary','shape'):value=(PARITY if rule=='parity' else THRESHOLD)[a]
            else:value=a
            out[r0:r0+nrows,:ncols]=value
        # Most tiles fit entirely in the file and need a single strided gather.
        last=(row_start+(rows-1)*row_step)*grid_width+col_start+(cols-1)*col_step
        if last<total:fill(0,rows,cols)
        else:
            for r in range(rows):
                start=(row_start+r*row_step)*grid_width+col_start
                n=min(cols,max(0,(total-1-start)//col_step+1));fill(r,1,n)
        return out.tobytes(),total
    def close(self):
        if hasattr(self,'mapping'):
            try:self.mapping.close()
            except (BufferError,OSError):pass
        if hasattr(self,'file'):self.file.close()
    def __del__(self):self.close()

def equal_files(a,b):
    first=DigitStore(a);second=DigitStore(b)
    try:
        if len(first)!=len(second):return False
        return all(first[start:start+4*1024*1024]==second[start:start+4*1024*1024] for start in range(0,len(first),4*1024*1024))
    finally:first.close();second.close()
