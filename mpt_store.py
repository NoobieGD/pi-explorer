"""Large-file-safe, bounded decoding of app-tagged TachusPI decimal MPT.

MPT layout: Fabrice Bellard's official tpidump.c. The native base field is
unused, so only files tagged by our verified decimal-output wrapper are opened.
The requested decimal count is stored in otherwise unused header padding.
"""
import mmap, struct
from pathlib import Path
import numpy as np
from ycd_store import YcdStore

HEADER = struct.Struct('<8sQQQQQq')
TAG = struct.Struct('<8sQQ')
TAG_OFFSET = 64
MAGIC = b'PIATLAS1'
MASK = (1 << 64) - 1

def tag_decimal_output(path, count):
    if isinstance(count,bool) or not isinstance(count,int) or not 1 <= count <= MASK:
        raise ValueError('Invalid decimal digit count')
    with Path(path).open('r+b') as f:
        f.seek(TAG_OFFSET)
        f.write(TAG.pack(MAGIC,count,count ^ MASK))
        f.flush()

class MptStore(YcdStore):
    def __init__(self,path):
        self.path=Path(path);self.file=self.path.open('rb')
        try:
            self.mapping=mmap.mmap(self.file.fileno(),0,access=mmap.ACCESS_READ)
            if len(self.mapping)<4096:raise ValueError('Truncated MPT header')
            magic,words,allocated,kind,negative,base,exponent=HEADER.unpack_from(self.mapping)
            marker,count,inverse=TAG.unpack_from(self.mapping,TAG_OFFSET)
            if magic!=b'MPT\x01FILE' or kind!=2 or negative or exponent!=1:
                raise ValueError('Unsupported decimal pi MPT header')
            if marker!=MAGIC or not count or inverse!=(count ^ MASK):
                raise ValueError('MPT needs a verified decimal-output tag from Pi Explorer')
            needed=(count+18)//19
            if words<needed+1 or allocated<words or 4096+allocated*8>len(self.mapping):
                raise ValueError('Truncated MPT payload')
            if struct.unpack_from('<Q',self.mapping,4096+(words-1)*8)[0]!=3:
                raise ValueError('Invalid MPT integer part')
            self.length=count
            self.offset=4096+(words-1-needed)*8
            self.version=f'mpt:{self.path.name}:{self.path.stat().st_mtime_ns}:{count}'
            from digit_store import PREFIX
            if self[:min(count,len(PREFIX))]!=PREFIX[:min(count,len(PREFIX))]:
                raise ValueError('Invalid pi prefix in MPT')
        except Exception:
            self.close();raise
    def _words(self):
        # A negative-stride mmap view reverses limb order without copying it.
        return np.ndarray((self.length+18)//19,dtype='<u8',buffer=self.mapping,offset=self.offset)[::-1]
