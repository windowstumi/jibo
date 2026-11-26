"""Local, reviewed action clips. Rendering/decoding stays in Chromium."""
import io
import hashlib
import json
import math
import re
import uuid

import numpy as np
from PIL import Image

from scene_model import write_json

KINDS = {'thanks': '答谢', 'greeting': '招手', 'present': '介绍'}
MAX_CLIP_BYTES = 20_000_000
MAX_PROJECT_BYTES = 100_000_000


def video_suffix(raw):
    if not 16 <= len(raw) <= MAX_CLIP_BYTES:
        raise ValueError('动作短片须小于20MB')
    if raw[4:8] == b'ftyp':
        return '.mp4'
    if raw[:4] == b'\x1aE\xdf\xa3':
        return '.webm'
    raise ValueError('仅支持 MP4 或 WebM 视频文件')


def load_actions(directory):
    path = directory / 'actions.json'
    actions = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
    if actions:
        digest = hashlib.sha256((directory/'neutral.png').read_bytes()).hexdigest()
        for record in actions.values():
            if record.get('reference_sha256') != digest:
                record['enabled'] = False
    return actions


def validate_record(kind, record):
    if kind not in KINDS or not isinstance(record, dict):
        raise ValueError('未知动作类型')
    if not re.fullmatch(r'action-[a-f0-9]{32}\.(mp4|webm)', record.get('file', '')):
        raise ValueError('动作文件名无效')
    duration = record.get('duration', 0)
    if not isinstance(duration, (int, float)) or not math.isfinite(duration) or not 1 <= duration <= 8:
        raise ValueError('动作时长须为1至8秒')
    if record.get('background') not in ('green', 'transparent'):
        raise ValueError('请选择绿幕或透明背景')
    width, height = record.get('width', 0), record.get('height', 0)
    if not isinstance(width, int) or not isinstance(height, int) or not 64 <= width <= 2048 or not 64 <= height <= 2048 or width * height > 2_500_000:
        raise ValueError('视频尺寸过大或无效，请使用不超过2048边长、250万像素的短片')
    return {k: record[k] for k in ('file', 'duration', 'background', 'width', 'height')} | {
        'enabled': record.get('enabled') is True, 'reference_sha256':record.get('reference_sha256','')}


def endpoint_score(raw, neutral, background):
    with Image.open(io.BytesIO(raw)) as im:
        if im.format != 'PNG' or im.width * im.height > 2_500_000:
            raise ValueError('首尾帧须为视频截取的PNG图片')
        frame = im.convert('RGBA')
        if abs(frame.width / frame.height - neutral.width / neutral.height) > .03:
            raise ValueError('视频宽高比必须与标准角色图一致')
        frame = frame.resize((128, 128))
    ref = np.asarray(neutral.resize((128, 128)), dtype=float) / 255
    pixels = np.asarray(frame, dtype=float) / 255
    if background == 'green':
        excess = pixels[:, :, 1] - np.maximum(pixels[:, :, 0], pixels[:, :, 2])
        pixels[:, :, 3] *= 1 - np.clip((excess - .08) / .22, 0, 1)
    a, b = ref[:, :, 3], pixels[:, :, 3]
    union = np.maximum(a, b).sum()
    overlap = np.minimum(a, b).sum() / max(1, union)
    foreground = (a > .8) & (b > .8)
    color = float(np.abs(ref[:, :, :3] - pixels[:, :, :3])[foreground].mean()) if foreground.any() else 1.
    if overlap < .8 or color > .2:
        raise ValueError('首尾姿态或角色外观与标准图差异过大，请让短片首尾回到标准姿态后再导入')
    return {'overlap': round(float(overlap), 3), 'color_error': round(color, 3)}


def save_action(directory, kind, raw, metadata, first, last):
    suffix = video_suffix(raw)
    record = validate_record(kind, metadata | {'file': 'action-' + uuid.uuid4().hex + suffix, 'enabled': False})
    with Image.open(directory / 'neutral.png') as image:
        neutral = image.convert('RGBA')
    if abs(record['width'] / record['height'] - neutral.width / neutral.height) > .03:
        raise ValueError('视频宽高比必须与标准角色图一致')
    checks = [endpoint_score(frame, neutral, record['background']) for frame in (first, last)]
    record['endpoint_checks'] = checks
    record['reference_sha256'] = hashlib.sha256((directory/'neutral.png').read_bytes()).hexdigest()
    actions = load_actions(directory)
    (directory / record['file']).write_bytes(raw)
    actions[kind] = record
    write_json(directory / 'actions.json', actions)
    return actions
