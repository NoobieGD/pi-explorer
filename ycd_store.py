"""Read decimal y-cruncher YCD directly: 19 digits per little-endian uint64.

Format reference: Alexander Yee's open-source Mysticial/DigitViewer reader.
This implementation supports one complete decimal file (BlockID 0); it refuses
partial multi-file sets. No full text expansion is written to disk.
"""
import mmap
from pathlib import Path
import numpy as np

FOUR=np.frombuffer(''.join(f'{i:04d}' for i in range(10000)).encode(),dtype=np.uint8).reshape(-1,4)
THREE=FOUR[:1000,1:]
POWERS=np.array([10**i for i in range(19)],dtype=np.uint64)

class YcdStore:
    packed=True
    def __init__(self,path,constant=None):
        self.path=Path(path);self.file=self.path.open('rb')
        try:
            from constants import infer,CONSTANTS
            self.constant=infer(path,constant);spec=CONSTANTS[self.constant];self.integerPart=spec['integer']
            self.mapping=mmap.mmap(self.file.fileno(),0,access=mmap.ACCESS_READ)
            head=self.mapping[:65536];end=head.find(b'\0')
            if end<0 or not head.startswith(b'#Compressed Digit File'):raise ValueError('Invalid YCD header')
            fields={}
            for line in head[:end].decode('ascii').splitlines():
                if '\t' in line:
                    key,value=line.split('\t',1);fields[key.rstrip(':')]=value.strip()
            if fields.get('FileVersion') not in ('1.0.0','1.1.0') or fields.get('Base')!='10':raise ValueError('Unsupported YCD version or radix')
            block=int(fields['Blocksize']);total=int(fields['TotalDigits']);identity=int(fields['BlockID'])
            if identity!=0 or block<1 or total>block:raise ValueError('Open a complete single-file decimal YCD, not a split set')
            self.length=min(block,total) if total else block;self.offset=end+1
            if self.offset+((self.length+18)//19)*8>len(self.mapping):raise ValueError('Truncated YCD payload')
            self.version=f'ycd:{self.path.name}:{self.path.stat().st_mtime_ns}:{self.length}'
            if self[:min(self.length,50)]!=spec['prefix'][:min(self.length,50)].encode():raise ValueError('Invalid '+self.constant+' prefix in YCD')
        except Exception:self.close();raise
    def __len__(self):return self.length
    def __bool__(self):return self.length>0
    def _words(self):
        return np.ndarray((self.length+18)//19,dtype='<u8',buffer=self.mapping,offset=self.offset)
    def __getitem__(self,key):
        if not isinstance(key,slice):
            if key<0:key+=self.length
            if not 0<=key<self.length:raise IndexError(key)
            return self[key:key+1][0]
        start,end,step=key.indices(self.length)
        if step!=1:raise ValueError('Use contiguous digit windows')
        if end<=start:return b''
        lo=start//19;hi=(end+18)//19
        words=self._words()[lo:hi]
        if np.any(words>=10**19):raise ValueError('Invalid decimal word in YCD')
        out=np.empty((len(words),19),dtype=np.uint8)
        for at,divisor in ((0,10**15),(4,10**11),(8,10**7),(12,1000)):
            out[:,at:at+4]=FOUR[(words//np.uint64(divisor)%10000).astype(np.intp)]
        out[:,16:]=THREE[(words%1000).astype(np.intp)]
        return out.reshape(-1)[start-lo*19:end-lo*19].tobytes()
    def chunks(self,size=4*1024*1024):
        for start in range(0,self.length,size):yield self[start:min(self.length,start+size)]
    def total_units(self,mode='digits',scheme='mod26',alignment=0):
        from digit_store import unit_step
        return max(0,(self.length-(alignment if mode=='text' else 0))//unit_step(mode,scheme))
    def window(self,start,count,mode='digits',scheme='mod26',rule='threshold',alignment=0):
        from digit_store import unit_step,transform
        step=unit_step(mode,scheme);a=alignment if mode=='text' else 0;total=self.total_units(mode,scheme,alignment)
        start=min(max(0,start),total);count=min(max(0,count),total-start)
        return transform(self[a+start*step:a+(start+count)*step],mode,scheme,rule),total
    def tile(self,grid_width,row_start,col_start,rows,cols,row_step=1,col_step=1,mode='digits',scheme='mod26',rule='threshold',alignment=0):
        from digit_store import unit_step,PAIR_MOD,PAIR_A1,ASCII,PARITY,THRESHOLD
        total=self.total_units(mode,scheme,alignment);out=np.full((rows,cols),32,dtype=np.uint8)
        units=(row_start+np.arange(rows,dtype=np.int64)[:,None]*row_step)*grid_width+col_start+np.arange(cols,dtype=np.int64)*col_step
        valid=units<total
        if not np.any(valid):return out.tobytes(),total
        step=unit_step(mode,scheme);positions=units[valid]*step+(alignment if mode=='text' else 0)
        def gather(pos):
            values=self._words()[pos//19]
            if np.any(values>=10**19):raise ValueError('Invalid decimal word in YCD')
            return ((values//POWERS[18-pos%19])%10).astype(np.uint16)
        value=gather(positions)
        if mode=='text':
            value=value*10+gather(positions+1)
            value=ASCII[value*10+gather(positions+2)] if scheme=='ascii' else (PAIR_A1 if scheme=='a1z26' else PAIR_MOD)[value]
        elif mode in ('binary','shape'):value=(PARITY if rule=='parity' else THRESHOLD)[value+48]
        else:value+=48
        out[valid]=value;return out.tobytes(),total
    def find(self,query,start=0,end=None):
        end=self.length if end is None else min(end,self.length);block=4*1024*1024
        for lo in range(start,end,block):
            at=self[lo:min(end,lo+block+len(query)-1)].find(query)
            if at>=0:return lo+at
        return -1
    def close(self):
        if hasattr(self,'mapping'):
            try:self.mapping.close()
            except (BufferError,OSError):pass
        if hasattr(self,'file'):self.file.close()
    def __del__(self):self.close()
