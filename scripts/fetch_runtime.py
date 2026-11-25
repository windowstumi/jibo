"""Fetch the optional official PSD2Live runtime into this checkout only."""
import hashlib
import json
from pathlib import Path
import sys
import zipfile

import httpx

ROOT=Path(__file__).resolve().parent.parent

def digest(path):
    h=hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def fetch(name):
    spec=json.loads((ROOT/'runtime.versions.json').read_text(encoding='utf-8'))[name]
    target=ROOT/'.runtime'/f'{name}-{spec["version"]}'
    if (target/'runtime/bin/java.exe').is_file():return
    cache=ROOT/'.runtime/downloads';cache.mkdir(parents=True,exist_ok=True)
    archive=cache/f'{name}.zip'
    if not archive.is_file() or digest(archive)!=spec['sha256']:
        part=cache/f'{name}.zip.part'
        marker=cache/f'{name}.zip.part.sha256'
        if not marker.is_file() or marker.read_text()!=spec['sha256'] or (part.exists() and part.stat().st_size>spec['size']):
            part.write_bytes(b'')
            marker.write_text(spec['sha256'])
        errors=[]
        for url in [spec['api_url'],spec['url']]:
            try:
                # Range requests also work through proxies that cap response size.
                with httpx.Client(follow_redirects=True,timeout=httpx.Timeout(90,connect=20)) as client,part.open('ab') as out:
                    position=part.stat().st_size
                    download_url=url
                    while position<spec['size']:
                        end=min(position+8*1024*1024,spec['size'])-1
                        with client.stream('GET',download_url,headers={'Accept':'application/octet-stream','User-Agent':'jibo-bootstrap','Range':f'bytes={position}-{end}'}) as response:
                            response.raise_for_status()
                            if 'application/json' in response.headers.get('Content-Type',''):
                                raise ValueError('Download endpoint returned metadata instead of the runtime archive')
                            download_url=str(response.url)
                            if response.status_code==206:
                                content_range=response.headers.get('Content-Range','')
                                if not content_range.startswith(f'bytes {position}-'):raise ValueError('Server returned the wrong byte range')
                            elif position:raise ValueError('Server ignored the resume range')
                            received=0
                            for chunk in response.iter_bytes():out.write(chunk);received+=len(chunk)
                            if not received:raise ValueError('Empty runtime response')
                            position+=received
                            if position>spec['size']:raise ValueError('Unexpected runtime size')
                            print(f'{name}: {position}/{spec["size"]} bytes',flush=True)
                if digest(part)!=spec['sha256']:
                    part.write_bytes(b'')
                    raise ValueError('Runtime SHA256 mismatch')
                part.replace(archive);break
            except Exception as error:errors.append(str(error))
        else:raise RuntimeError('Could not download verified runtime: '+'; '.join(errors))
    target.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(archive) as bundle:
        for entry in bundle.infolist():
            dest=(target/entry.filename).resolve()
            if not dest.is_relative_to(target.resolve()):raise ValueError('Unsafe path in runtime archive')
        bundle.extractall(target)
    if not (target/'runtime/bin/java.exe').is_file():raise RuntimeError('Runtime archive has an unexpected layout')
    print(f'Installed {name} {spec["version"]}: {target}')

if __name__=='__main__':fetch(sys.argv[1])
