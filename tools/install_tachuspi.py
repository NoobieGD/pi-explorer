"""Personal install from the author's official archive; do not redistribute it."""
from pathlib import Path
import hashlib, io, urllib.request, zipfile, os
ROOT=Path(__file__).resolve().parents[1]
URL='https://bellard.org/pi/pi2700e9/tpi-0.9.3-win.zip'
SHA256='aab1a9caebed62954b7b31186b65e86ec8722559197b9dc4e3804c4b3722d296'

def install():
    if os.name!='nt':raise RuntimeError('This installer is for the official Windows build.')
    with urllib.request.urlopen(URL,timeout=30) as response:
        data=response.read(4*1024*1024)
    if hashlib.sha256(data).hexdigest()!=SHA256:raise ValueError('Official archive checksum changed; nothing installed.')
    target=ROOT/'vendor/tachuspi';target.mkdir(exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        for name in ('tpi.exe','README','Changelog'):
            temp=target/(name+'.download')
            temp.write_bytes(archive.read(name));os.replace(temp,target/name)
    print('TachusPI installed locally. Restart Pi Explorer. No calculation started.')

if __name__=='__main__':install()
