"""Optional, project-owned GPT-SoVITS inference component and voice packages."""
import asyncio
import contextlib
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import uuid
import wave
import zipfile

import httpx

ASSETS = (Path(sys._MEIPASS) / 'local_tts' if getattr(sys, 'frozen', False)
          else Path(__file__).resolve().parent / 'tools/local_tts')
DEFAULT_LOCAL = {'voice_id': 'cao', 'auto_load': True, 'speed': 1.0, 'package_index': 'tuna'}
MAX_VOICE_PACKAGE = 600_000_000


def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def safe_extract(archive, target, strip_first=False):
    target = target.resolve()
    with zipfile.ZipFile(archive) as bundle:
        if sum(item.file_size for item in bundle.infolist()) > 8_000_000_000:
            raise ValueError('解压后的组件过大')
        for item in bundle.infolist():
            name = item.filename.replace('\\', '/')
            parts = PurePosixPath(name).parts
            if name.startswith('/') or '..' in parts or any(':' in part for part in parts):
                raise ValueError('压缩包包含无效路径')
            if strip_first:
                parts = parts[1:]
            if not parts:
                continue
            path = target.joinpath(*parts)
            if not path.resolve().is_relative_to(target):
                raise ValueError('压缩包不能写入组件目录之外')
            if item.is_dir():
                path.mkdir(parents=True, exist_ok=True)
            else:
                path.parent.mkdir(parents=True, exist_ok=True)
                with bundle.open(item) as source, path.open('wb') as output:
                    shutil.copyfileobj(source, output)


def inspect_voice(raw):
    if len(raw) > MAX_VOICE_PACKAGE:
        raise ValueError('音色包不能超过600MB')
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        infos = bundle.infolist()
        if len(infos) > 12 or sum(item.file_size for item in infos) > 1_000_000_000:
            raise ValueError('音色包内容过大')
        names = [item.filename for item in infos]
        if len(names) != len(set(names)) or 'voice.json' not in names:
            raise ValueError('音色包缺少唯一的 voice.json')
        meta_info = bundle.getinfo('voice.json')
        if meta_info.file_size > 32768:
            raise ValueError('音色清单过大')
        meta = json.loads(bundle.read('voice.json'))
        if not isinstance(meta, dict) or meta.get('schema') != 1 or meta.get('version') != 'v2':
            raise ValueError('当前支持 schema=1 的 GPT-SoVITS v2 音色包')
        if not isinstance(meta.get('name'), str) or not 1 <= len(meta['name']) <= 60:
            raise ValueError('音色名称无效')
        if not isinstance(meta.get('prompt_text'), str) or not 1 <= len(meta['prompt_text']) <= 500:
            raise ValueError('请提供准确的参考录音文字')
        expected = {'voice.json', 'VOICE-LICENSE.txt'}
        for key, suffixes in [('gpt', {'.ckpt'}), ('sovits', {'.pth'}), ('reference', {'.wav'})]:
            entry = meta.get(key, {})
            if not isinstance(entry, dict):
                raise ValueError('音色文件清单格式无效')
            name = entry.get('file', '')
            if not isinstance(name, str) or '/' in name or '\\' in name or ':' in name or Path(name).suffix not in suffixes:
                raise ValueError('音色文件必须位于包根目录并使用指定扩展名')
            if name not in names or bundle.getinfo(name).file_size > 500_000_000:
                raise ValueError('音色模型缺失或过大')
            raw_file = bundle.read(name)
            if hashlib.sha256(raw_file).hexdigest() != entry.get('sha256'):
                raise ValueError('音色文件校验失败')
            expected.add(name)
        if set(names) != expected or bundle.getinfo('VOICE-LICENSE.txt').file_size > 32768:
            raise ValueError('音色包文件不符合约定')
        with wave.open(io.BytesIO(bundle.read(meta['reference']['file']))) as audio:
            duration = audio.getnframes() / audio.getframerate()
            if audio.getcomptype() != 'NONE' or not 3 <= duration <= 10:
                raise ValueError('参考录音须为3至10秒 PCM WAV')
        return meta


class LocalTTS:
    def __init__(self, data, get_settings, notify=lambda state: None, assets=ASSETS):
        self.root = Path(data).resolve() / 'local-tts'
        self.assets = assets
        self.get_settings = get_settings
        self.notify = notify
        self.manifest = json.loads((assets / 'component.json').read_text(encoding='utf-8'))
        self.task = None
        self.process = None
        self.installer_process = None
        self.log_handle = None
        self.port = None
        self.loaded_voice = None
        self.cancel = threading.Event()
        self.loop = None
        self.state = {'phase': 'idle', 'message': '本地语音尚未加载', 'progress': None, 'error': None}

    @property
    def python(self):
        return self.root / 'venv/Scripts/python.exe'

    @property
    def engine(self):
        return self.root / 'engine'

    def fingerprint(self):
        return hashlib.sha256((self.assets / 'component.json').read_bytes() +
                              (self.assets / 'requirements.lock.txt').read_bytes() +
                              str(self.root).encode()).hexdigest()

    def installed(self):
        try:
            return (self.python.is_file() and (self.engine / 'api_v2.py').is_file() and
                    json.loads((self.root / 'installed.json').read_text())['fingerprint'] == self.fingerprint())
        except (OSError, KeyError, ValueError):
            return False

    def voices(self):
        result = []
        folder = self.root / 'voices'
        if folder.exists():
            for path in sorted(folder.glob('*/voice.json')):
                if path.parent.name.startswith('.'):
                    continue
                with contextlib.suppress(OSError, ValueError, KeyError):
                    meta = json.loads(path.read_text(encoding='utf-8'))
                    result.append({'id': path.parent.name, 'name': meta['name'], 'version': meta['version']})
        return result

    def snapshot(self):
        return {**self.state, 'installed': self.installed(), 'voices': self.voices(),
                'loaded_voice': self.loaded_voice, 'component': self.manifest['component'],
                'supported': sys.platform == 'win32'}

    def update(self, phase, message, progress=None, **values):
        self.state = {'phase': phase, 'message': message, 'progress': progress, 'error': None, **values}
        if self.loop and not self.loop.is_closed():
            self.loop.call_soon_threadsafe(self.notify, self.snapshot())

    def import_voice(self, raw, builtin=False):
        meta = inspect_voice(raw)
        ident = 'cao' if builtin else uuid.uuid4().hex
        target = self.root / 'voices' / ident
        if target.exists():
            raise ValueError('该音色已经安装')
        staging = self.root / 'voices' / ('.import-' + uuid.uuid4().hex)
        staging.mkdir(parents=True)
        try:
            safe_extract(io.BytesIO(raw), staging)
            staging.rename(target)
        finally:
            if staging.exists() and staging.resolve().is_relative_to((self.root / 'voices').resolve()):
                shutil.rmtree(staging)
        return {'id': ident, 'name': meta['name'], 'version': meta['version']}

    def _default_voice(self):
        if (self.root / 'voices/cao/voice.json').is_file():
            return
        resources = Path(os.environ.get('JIBO_RESOURCE_DIR', Path(__file__).parent / 'build'))
        pack = resources / 'local-tts/default-voice.zip'
        if pack.is_file():
            self.import_voice(pack.read_bytes(), builtin=True)

    def _download(self, spec, target, message):
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.is_file() and digest(target) == spec['sha256']:
            self.update('installing', message + '（已校验缓存）', 100)
            return target
        part = target.with_suffix(target.suffix + '.part')
        errors = []
        for url in spec['urls']:
            for attempt in range(2):
                try:
                    if spec.get('size', 0) > 64 * 1024 * 1024:
                        self._ranged(url, spec, part, message)
                        if digest(part) != spec['sha256']:
                            part.unlink(missing_ok=True)
                            for chunk in part.parent.glob(part.name + '.' + spec['sha256'][:12] + '.*.chunk'):
                                chunk.unlink()
                            raise ValueError('下载文件的 SHA256 校验失败')
                        part.replace(target)
                        return target
                    offset = part.stat().st_size if part.exists() else 0
                    if spec.get('size') and offset >= spec['size']:
                        if digest(part) == spec['sha256']:
                            part.replace(target)
                            return target
                        part.unlink()
                        offset = 0
                    request = urllib.request.Request(url, headers={'User-Agent': 'Jibo-Local-TTS',
                        'Accept': 'application/octet-stream', **spec.get('headers', {}),
                        **({'Range': f'bytes={offset}-'} if offset else {})})
                    with urllib.request.urlopen(request, timeout=60) as response:
                        if offset and response.status != 206:
                            offset = 0
                        if response.status == 206 and not response.headers.get('Content-Range', '').startswith(f'bytes {offset}-'):
                            raise ValueError('下载服务器返回了错误的断点范围')
                        total = spec.get('size') or (int(response.headers.get('Content-Length', 0)) + offset)
                        count = offset
                        last = 0
                        with part.open('ab' if offset else 'wb') as stream:
                            while True:
                                if self.cancel.is_set():
                                    raise InterruptedError('安装已停止，可在下次启动时继续')
                                block = response.read(1024 * 1024)
                                if not block:
                                    break
                                stream.write(block)
                                count += len(block)
                                if time.monotonic() - last > .4:
                                    self.update('installing', message, round(count / total * 100, 1) if total else None,
                                                downloaded_bytes=count, total_bytes=total)
                                    last = time.monotonic()
                    if digest(part) != spec['sha256']:
                        part.unlink(missing_ok=True)
                        raise ValueError('下载文件的 SHA256 校验失败')
                    part.replace(target)
                    return target
                except InterruptedError:
                    raise
                except Exception as error:
                    errors.append(str(error))
        raise RuntimeError(message + '失败：' + errors[-1])

    def _ranged(self, url, spec, part, message):
        chunk_size = 64 * 1024 * 1024
        count = (spec['size'] + chunk_size - 1) // chunk_size
        downloaded = {}
        mutex = threading.Lock()
        last = [0.0]
        def fetch(index):
            start = index * chunk_size
            end = min(spec['size'], start + chunk_size) - 1
            chunk = part.parent / f'{part.name}.{spec["sha256"][:12]}.{index}.chunk'
            expected = end - start + 1
            if chunk.is_file() and chunk.stat().st_size == expected:
                with mutex:
                    downloaded[index] = expected
                return chunk
            request = urllib.request.Request(url, headers={'User-Agent': 'Jibo-Local-TTS',
                'Accept': 'application/octet-stream', 'Range': f'bytes={start}-{end}'})
            with urllib.request.urlopen(request, timeout=90) as response:
                if response.status != 206 or not response.headers.get('Content-Range', '').startswith(f'bytes {start}-'):
                    raise ValueError('下载源不支持正确的分段下载，请切换下载源')
                received = 0
                with chunk.open('wb') as output:
                    while True:
                        if self.cancel.is_set():
                            raise InterruptedError('安装已停止，可再次运行继续')
                        block = response.read(1024 * 1024)
                        if not block:
                            break
                        output.write(block)
                        received += len(block)
                        if received > expected:
                            raise ValueError('下载分段超出预期大小')
                        with mutex:
                            downloaded[index] = received
                            if time.monotonic() - last[0] > .4:
                                total = sum(downloaded.values())
                                self.update('installing', message, round(total / spec['size'] * 100, 1),
                                            downloaded_bytes=total, total_bytes=spec['size'])
                                last[0] = time.monotonic()
            if received != expected:
                raise ValueError('下载分段被截断，可再次运行继续')
            return chunk
        paths = {}
        with ThreadPoolExecutor(max_workers=4) as pool:
            tasks = {pool.submit(fetch, index): index for index in range(count)}
            for task in as_completed(tasks):
                paths[tasks[task]] = task.result()
        with part.open('wb') as output:
            for index in range(count):
                with paths[index].open('rb') as source:
                    shutil.copyfileobj(source, output)
        for path in paths.values():
            path.unlink()

    def _command(self, args, env, message):
        self.update('installing', message)
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        with (self.root / 'install.log').open('a', encoding='utf-8') as output:
            process = subprocess.Popen([str(arg) for arg in args], env=env, stdin=subprocess.DEVNULL,
                                       stdout=subprocess.PIPE, stderr=subprocess.STDOUT, creationflags=flags)
            self.installer_process = process
            try:
                for line in iter(process.stdout.readline, b''):
                    output.write(line.decode('utf-8', 'replace'))
                    output.flush()
                    if self.cancel.is_set():
                        self._kill(process)
                        raise InterruptedError('安装已停止')
                if process.wait() != 0:
                    raise RuntimeError(message + '失败，详见本地语音目录的 install.log')
            finally:
                self.installer_process = None

    def _install(self):
        if sys.platform != 'win32':
            raise ValueError('本地音色组件当前仅支持 Windows x64 与 NVIDIA 显卡')
        self.root.mkdir(parents=True, exist_ok=True)
        flags = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
        gpu = subprocess.run(['nvidia-smi', '--query-gpu=name,driver_version', '--format=csv,noheader'],
                             capture_output=True, text=True, creationflags=flags, timeout=15)
        if gpu.returncode:
            raise ValueError('未检测到 NVIDIA 驱动，请先安装或更新显卡驱动')
        self.update('installing', '正在准备 NVIDIA 推理组件', gpu=gpu.stdout.strip())
        cache = self.root / 'downloads'
        uv_archive = self._download(self.manifest['uv'], cache / 'uv.zip', '下载环境安装器')
        uv_root = self.root / 'uv'
        if not (uv_root / 'uv.exe').is_file():
            safe_extract(uv_archive, uv_root)
        uv = uv_root / 'uv.exe'
        env = {**os.environ, 'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1',
               'UV_PYTHON_INSTALL_DIR': str(self.root / 'python'), 'UV_PYTHON_BIN_DIR': str(self.root / 'bin'),
               'UV_CACHE_DIR': str(self.root / 'cache'), 'UV_HTTP_TIMEOUT': '600', 'UV_NO_PROGRESS': '1',
               'UV_PYTHON_PREFERENCE': 'only-managed'}
        for name in ('PYTHONHOME', 'PYTHONPATH', 'VIRTUAL_ENV'):
            env.pop(name, None)
        # uv does not consistently read Windows' Internet Settings proxy.
        # Forward it only to installer children, leaving system settings alone.
        proxies = urllib.request.getproxies()
        for scheme in ('http', 'https'):
            if proxies.get(scheme):
                env.setdefault(scheme.upper() + '_PROXY', proxies[scheme])
        env['NO_PROXY'] = ','.join(filter(None, [env.get('NO_PROXY', ''), '127.0.0.1,localhost,::1']))
        self._command([uv, 'python', 'install', '--no-bin', '--no-registry', self.manifest['python']], env,
                      '正在安装独立 Python 环境')
        valid_python = False
        if self.python.is_file():
            check = subprocess.run([str(self.python), '-c', 'import sys,json;print(json.dumps([sys.prefix,sys.base_prefix]))'],
                                   capture_output=True, text=True, creationflags=flags, timeout=15)
            try:
                prefix, base = json.loads(check.stdout)
                valid_python = (check.returncode == 0 and Path(prefix).resolve() == self.python.parents[1].resolve()
                                and Path(base).resolve().is_relative_to((self.root / 'python').resolve()))
            except (ValueError, TypeError):
                pass
        if not valid_python:
            venv = self.root / 'venv'
            if venv.exists():
                backup = self.root / ('previous-venv-' + uuid.uuid4().hex)
                if venv.is_symlink() or venv.is_junction() or not venv.resolve().is_relative_to(self.root):
                    raise ValueError('虚拟环境路径无效，不能迁移组件目录之外的环境')
                venv.rename(backup)
            self._command([uv, 'venv', '--python', self.manifest['python'], self.root / 'venv'], env,
                          '正在创建本地语音环境')
        index = ('https://pypi.tuna.tsinghua.edu.cn/simple' if
                 self.get_settings()['local_tts']['package_index'] == 'tuna' else 'https://pypi.org/simple')
        torch = self.manifest['torch']
        wheel = self._download(torch, cache / torch['name'], '下载 NVIDIA PyTorch 运行库')
        locked = (self.assets / 'requirements.lock.txt').read_text(encoding='utf-8')
        locked = locked.replace(torch['locked_url'], wheel.as_uri() + '#sha256=' + torch['sha256'])
        runtime_lock = self.root / 'requirements-installed.txt'
        runtime_lock.write_text(locked, encoding='utf-8')
        self._command([uv, 'pip', 'sync', '--python', self.python, '--no-cache', '--require-hashes', '--index-url', index,
                       runtime_lock], env,
                      '正在下载并安装 NVIDIA 推理依赖（首次需要数GB，可查看 install.log）')
        source = self._download(self.manifest['engine'], cache / 'engine.zip', '下载 GPT-SoVITS 推理代码')
        if not (self.engine / 'api_v2.py').is_file():
            safe_extract(source, self.engine, strip_first=True)
        for number, spec in enumerate(self.manifest['models'], 1):
            model_file = self._download(spec, self.engine / spec['path'], f'下载公共模型 {number}/{len(self.manifest["models"])}：{spec["name"]}')
            if spec.get('extract'):
                safe_extract(model_file, model_file.parent)
        g2pw = self.engine / 'GPT_SoVITS/text/G2PWModel'
        if not (g2pw / 'g2pW.onnx').is_file():
            archive = self._download(self.manifest['g2pw'], cache / 'g2pw.zip', '下载中文发音模型')
            safe_extract(archive, g2pw, strip_first=True)
        self._default_voice()
        self._command([self.python, '-c',
            'import imageio_ffmpeg,subprocess;print(imageio_ffmpeg.get_ffmpeg_exe());subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),"-version"],check=True)'],
            env, '正在检查音频工具与运行环境')
        (self.root / 'installed.json').write_text(json.dumps({'fingerprint': self.fingerprint(),
            'component': self.manifest['component'], 'gpu': gpu.stdout.strip()}, ensure_ascii=False), encoding='utf-8')

    async def start(self, install=False):
        self.loop = asyncio.get_running_loop()
        if self.task and not self.task.done():
            return self.snapshot()
        self.cancel.clear()
        self.task = asyncio.create_task(self._prepare(install))
        return self.snapshot()

    async def _prepare(self, install):
        try:
            await self.stop_native()
            if install or not self.installed():
                await asyncio.to_thread(self._install)
            else:
                await asyncio.to_thread(self._default_voice)
            await self._load()
        except asyncio.CancelledError:
            raise
        except Exception as error:
            await self.stop_native()
            self.update('error', '本地语音未就绪', error=str(error))

    async def _load(self):
        cfg = self.get_settings()['local_tts']
        voices = self.voices()
        ident = cfg['voice_id']
        if ident not in {item['id'] for item in voices}:
            raise ValueError('请在设置中导入或选择已安装的音色包')
        directory = self.root / 'voices' / ident
        voice = json.loads((directory / 'voice.json').read_text(encoding='utf-8'))
        config = {'custom': {'device': 'cuda', 'is_half': True, 'version': voice['version'],
            't2s_weights_path': str(directory / voice['gpt']['file']),
            'vits_weights_path': str(directory / voice['sovits']['file']),
            'bert_base_path': str(self.engine / 'GPT_SoVITS/pretrained_models/chinese-roberta-wwm-ext-large'),
            'cnhuhbert_base_path': str(self.engine / 'GPT_SoVITS/pretrained_models/chinese-hubert-base')}}
        config_path = self.root / 'active-voice.yaml'
        config_path.write_text(json.dumps(config, ensure_ascii=False, indent=2), encoding='utf-8')
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            self.port = sock.getsockname()[1]
        self.log_handle = (self.root / 'service.log').open('w', encoding='utf-8')
        self.process = subprocess.Popen([str(self.python), str(self.assets / 'native_worker.py'),
            '--engine', str(self.engine), '--config', str(config_path), '--port', str(self.port)],
            env={**os.environ, 'PYTHONUTF8': '1', 'PYTHONUNBUFFERED': '1'}, stdin=subprocess.PIPE,
            stdout=self.log_handle, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        self.update('loading', '正在加载音色：' + voice['name'])
        deadline = time.monotonic() + 240
        previous_phase = None
        async with httpx.AsyncClient(trust_env=False, timeout=2) as client:
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    tail = (self.root / 'service.log').read_text(encoding='utf-8', errors='replace')[-6000:]
                    reason = next((line for line in reversed(tail.splitlines()) if 'Error:' in line), '')
                    raise ValueError('语音引擎启动失败，请点击重新安装。' + (reason[:200] or '请查看 service.log，并确认 NVIDIA 驱动支持 CUDA 12.8'))
                tail = (self.root / 'service.log').read_text(encoding='utf-8', errors='replace')[-16000:]
                current_phase = None
                phases = [('Loading CNHuBERT', '正在加载语音编码器'), ('Loading BERT', '正在加载中文文本模型'),
                          ('Loading VITS', '正在加载音色模型'), ('Loading Text2Semantic', '正在加载说话模型')]
                for marker, title in phases:
                    if marker in tail:
                        current_phase = title
                        break
                if current_phase is None:
                    markers = [line.split('JIBO_PHASE: ', 1)[1] for line in tail.splitlines() if 'JIBO_PHASE: ' in line]
                    current_phase = markers[-1] if markers else None
                if current_phase and current_phase != previous_phase:
                    self.update('loading', current_phase + ' · ' + voice['name'])
                    previous_phase = current_phase
                try:
                    response = await client.get(f'http://127.0.0.1:{self.port}/openapi.json')
                    if response.status_code == 200 and '/tts' in response.json()['paths']:
                        break
                except (httpx.HTTPError, ValueError, KeyError):
                    pass
                await asyncio.sleep(.5)
            else:
                raise ValueError('本地语音加载超时，请查看 service.log')
        self.loaded_voice = ident
        self.update('warming', '正在预热音色，首次加载可能稍慢')
        await self._speech('你好，语音已经准备好了。支持USB商品介绍。', cfg)
        # Keep interrupted pieces for resume, but release multi-GB installers
        # only after a real successful synthesis proves the component works.
        def trim_installers():
            cache = self.root / 'downloads'
            for filename in (self.manifest['torch']['name'], 'g2pw.zip'):
                with contextlib.suppress(OSError):
                    (cache / filename).unlink(missing_ok=True)
        await asyncio.to_thread(trim_installers)
        self.update('ready', '本地语音已就绪：' + voice['name'], 100)

    async def _speech(self, text, cfg):
        directory = self.root / 'voices' / self.loaded_voice
        meta = json.loads((directory / 'voice.json').read_text(encoding='utf-8'))
        payload = {'text': text, 'text_lang': 'zh', 'prompt_lang': 'zh',
            'ref_audio_path': str(directory / meta['reference']['file']), 'prompt_text': meta['prompt_text'],
            'text_split_method': 'cut5', 'batch_size': 1, 'media_type': 'wav', 'streaming_mode': False,
            'speed_factor': cfg['speed'], 'seed': 42, 'use_cuda_graph': True, 'use_flash_attention': False}
        async with httpx.AsyncClient(trust_env=False, timeout=90) as client:
            response = await client.post(f'http://127.0.0.1:{self.port}/tts', json=payload)
        if response.status_code != 200:
            detail = ''
            with contextlib.suppress(ValueError):
                body = response.json()
                detail = str(body.get('Exception') or body.get('message', ''))[:800]
            raise ValueError('本地语音合成失败：' + (detail or '请查看 service.log'))
        with wave.open(io.BytesIO(response.content)) as wav:
            if wav.getnframes() <= 0:
                raise ValueError('本地语音返回了空音频')
        return response.content

    async def synthesize(self, text, cfg):
        if (self.state['phase'] != 'ready' or self.loaded_voice != cfg['voice_id'] or
                not self.process or self.process.poll() is not None):
            await self.start()
            raise ValueError('本地语音正在加载，请等待设置页进度完成后再试')
        return await self._speech(text, cfg)

    @staticmethod
    def _kill(process):
        if process and process.poll() is None:
            if sys.platform == 'win32':
                subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'], capture_output=True,
                               creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0), timeout=10)
            else:
                process.terminate()

    async def stop_native(self):
        if self.process:
            if self.process.stdin:
                with contextlib.suppress(OSError):
                    self.process.stdin.close()
            try:
                await asyncio.to_thread(self.process.wait, timeout=4)
            except subprocess.TimeoutExpired:
                await asyncio.to_thread(self._kill, self.process)
            self.process = None
        self.loaded_voice = None
        self.port = None
        if self.log_handle:
            self.log_handle.close()
            self.log_handle = None

    async def close(self):
        self.cancel.set()
        if self.installer_process:
            await asyncio.to_thread(self._kill, self.installer_process)
        if self.task and not self.task.done():
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        await self.stop_native()
