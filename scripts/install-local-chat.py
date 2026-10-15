"""Install official Ollama locally, keep model data inside storage, pull Gemma E2B."""
from pathlib import Path
import json
import os
import subprocess
import time
import zipfile
import requests

ROOT=Path(__file__).resolve().parents[1]
STORE=ROOT/'storage'
DEST=STORE/'runtime/ollama'
STATUS=STORE/'local-chat-setup.json'


def status(**body):
    STATUS.write_text(json.dumps(body,indent=2))


def main():
    DEST.mkdir(parents=True,exist_ok=True)
    executable=DEST/'ollama.exe'
    if not executable.exists():
        release=requests.get('https://api.github.com/repos/ollama/ollama/releases/latest',timeout=30)
        release.raise_for_status()
        asset=next(a for a in release.json()['assets'] if a['name']=='ollama-windows-amd64.zip')
        archive=STORE/'runtime/ollama.zip'
        status(status='downloading_runtime',bytes_total=asset['size'])
        downloaded=0
        with requests.get(asset['browser_download_url'],stream=True,timeout=120) as response:
            response.raise_for_status()
            with archive.open('wb') as out:
                for chunk in response.iter_content(4*1024*1024):
                    out.write(chunk)
                    downloaded+=len(chunk)
                    status(status='downloading_runtime',bytes_downloaded=downloaded,bytes_total=asset['size'])
        with zipfile.ZipFile(archive) as z:
            for name in z.namelist():
                if not (DEST/name).resolve().is_relative_to(DEST.resolve()):
                    raise ValueError('Invalid runtime archive')
            z.extractall(DEST)
    environment={**os.environ,'OLLAMA_MODELS':str(STORE/'ollama/models'),'OLLAMA_HOST':'127.0.0.1:11434','OLLAMA_NUM_PARALLEL':'1','OLLAMA_MAX_LOADED_MODELS':'1','OLLAMA_FLASH_ATTENTION':'1','OLLAMA_KV_CACHE_TYPE':'q8_0'}
    try:
        requests.get('http://127.0.0.1:11434/api/tags',timeout=2).raise_for_status()
    except requests.RequestException:
        log=(STORE/'logs/ollama.log').open('a')
        subprocess.Popen([str(executable),'serve'],env=environment,stdout=log,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
        for _ in range(40):
            try:
                requests.get('http://127.0.0.1:11434/api/tags',timeout=2).raise_for_status()
                break
            except requests.RequestException:
                time.sleep(1)
    status(status='pulling_model',model='gemma4:e2b')
    with requests.post('http://127.0.0.1:11434/api/pull',json={'model':'gemma4:e2b','stream':True},stream=True,timeout=600) as response:
        response.raise_for_status()
        for line in response.iter_lines():
            if line:
                item=json.loads(line)
                if item.get('error'):
                    raise RuntimeError(item['error'])
                status(status='pulling_model',model='gemma4:e2b',progress=item)
    status(status='ready',model='gemma4:e2b',runtime=str(executable))


if __name__=='__main__':
    try:
        main()
    except Exception as exc:
        status(status='failed',error=str(exc))
        raise
