"""Package an authorized GPT-SoVITS v2 model pair for local import/release."""
import argparse
import hashlib
import json
from pathlib import Path
import zipfile


def build(gpt, sovits, reference, text, name, output):
    entries = {'gpt': (gpt, 'gpt.ckpt'), 'sovits': (sovits, 'sovits.pth'),
               'reference': (reference, 'reference.wav')}
    meta = {'schema': 1, 'name': name, 'version': 'v2', 'prompt_text': text}
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', zipfile.ZIP_DEFLATED, compresslevel=5) as bundle:
        for kind, (source, filename) in entries.items():
            meta[kind] = {'file': filename, 'sha256': hashlib.sha256(source.read_bytes()).hexdigest()}
            bundle.write(source, filename)
        bundle.writestr('voice.json', json.dumps(meta, ensure_ascii=False, indent=2))
        bundle.writestr('VOICE-LICENSE.txt', '本音色的录音及音色权重由项目用户提供。用户于2026-11-27声明为本人录制，允许随极播商业软件分发。基础模型、代码及依赖的许可见第三方许可说明。\n')
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('gpt', 'sovits', 'reference'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--text', required=True)
    parser.add_argument('--name', default='默认主播音色')
    parser.add_argument('--output', type=Path, default=Path('build/local-tts/default-voice.zip'))
    args = parser.parse_args()
    print(build(args.gpt, args.sovits, args.reference, args.text, args.name, args.output))
