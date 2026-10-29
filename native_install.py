"""Locate a separately installed official y-cruncher distribution."""
import os
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DEFAULT=ROOT/'vendor/y-cruncher/y-cruncher v0.8.7.9547b/y-cruncher.exe'
def find_native(root=ROOT):
 root=Path(root)
 explicit=os.environ.get('PI_EXPLORER_YCRUNCHER')
 if explicit:return Path(explicit).expanduser().resolve()
 preferred=root/'vendor/y-cruncher/y-cruncher v0.8.7.9547b/y-cruncher.exe'
 if preferred.is_file():return preferred
 candidates=[]
 for base in (root/'vendor',root/'y-cruncher'):
  if base.is_dir():candidates.extend(base.rglob('y-cruncher.exe'))
 if (root/'y-cruncher.exe').is_file():candidates.append(root/'y-cruncher.exe')
 if len(candidates)==1:return candidates[0].resolve()
 return preferred

def require_native(path=None):
 path=Path(path or find_native())
 if not path.is_file():raise FileNotFoundError('y-cruncher was not found. Extract the COMPLETE official distribution under vendor/y-cruncher (including its Binaries folder), or set PI_EXPLORER_YCRUNCHER to the full y-cruncher.exe path. Restart the app after installing. If several copies exist, select one with PI_EXPLORER_YCRUNCHER.')
 return path
