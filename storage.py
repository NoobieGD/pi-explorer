"""Atomic cache writes that tolerate short Windows read/antivirus locks."""
import os
import tempfile
import time
import json
from pathlib import Path

def atomic_write(path, text, encoding='utf-8', retries=24, delay=.015):
    path=Path(path)
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,name=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    temp=Path(name)
    try:
        with os.fdopen(fd,'w',encoding=encoding) as stream: stream.write(text)
        for attempt in range(retries):
            try:
                os.replace(temp,path)
                return
            except PermissionError:
                if attempt+1==retries: raise
                time.sleep(min(.15,delay*(attempt+1)))
    finally:
        try:temp.unlink(missing_ok=True)
        except OSError:pass

def write_progress(path,value,message,**extra):
    # Progress is advisory. A locked progress file must never fail arithmetic.
    try:
        atomic_write(path,json.dumps({'progress':value,'message':message,**extra}),retries=4,delay=.005)
        return True
    except OSError:
        return False
