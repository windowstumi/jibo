"""Image edit protocol and proxy handling, shared by diagnostics and generation."""
import base64
import binascii
import json
import re
import sys
import urllib.request
from urllib.parse import urlsplit

import httpx


def endpoint(base_url, route):
    base = base_url.strip().rstrip('/')
    for suffix in ('/images/edits', '/images/generations', '/models'):
        if base.endswith(suffix):
            base = base[:-len(suffix)]
            break
    return base + route


def system_proxies():
    # HTTPX reads environment variables, but not Windows Internet Settings.
    proxies = urllib.request.getproxies()
    if sys.platform == 'win32' and not proxies.get('https') and not proxies.get('http'):
        proxies.update(urllib.request.getproxies_registry())
    return proxies


def proxy_for(cfg):
    mode = cfg.get('proxy_mode', 'system')
    if mode == 'direct':
        return None
    if mode == 'manual':
        return cfg.get('proxy_url', '').strip() or None
    # Local model servers should never be sent through an internet proxy.
    if urlsplit(cfg['base_url']).hostname in ('127.0.0.1', 'localhost', '::1'):
        return None
    proxies = system_proxies()
    return proxies.get('https') or proxies.get('http') or proxies.get('all')


def image_client(cfg, timeout=180):
    return httpx.AsyncClient(proxy=proxy_for(cfg), trust_env=False,
                             timeout=httpx.Timeout(timeout, connect=15))


def safe_detail(text, cfg):
    text = str(text)
    for secret in (cfg.get('key'), cfg.get('proxy_url')):
        if secret:
            text = text.replace(secret, '[已隐藏]')
    text = re.sub(r'(?i)bearer\s+\S+|sk-[A-Za-z0-9_-]+', '[已隐藏]', text)
    return ' '.join(text.split())[:250]


def connection_error(exc, cfg):
    via = '当前代理' if proxy_for(cfg) else '直连网络'
    if isinstance(exc, httpx.ConnectTimeout):
        return f'连接图片服务超时（{via}）。请检查 API 地址、系统代理或手动代理。'
    if isinstance(exc, httpx.ReadTimeout):
        return '图片服务响应超时。生成可能仍在服务端进行，请先查服务后台，避免重复扣费。'
    if isinstance(exc, httpx.ProxyError):
        return '无法连接代理。请确认代理程序正在运行，且代理地址和端口正确。'
    if isinstance(exc, httpx.ConnectError):
        causes = str(exc).lower()
        if 'certificate' in causes or 'ssl' in causes:
            return '图片服务的 TLS 证书校验失败。请检查服务证书和代理证书配置。'
        return f'无法连接图片服务（{via}）。请检查 API 地址、网络及代理设置。'
    return '图片请求传输中断。请检查网络连接；重试前确认服务后台是否已生成图片。'


def response_json(response, cfg):
    try:
        body = response.json()
    except (ValueError, json.JSONDecodeError):
        body = None
    if response.status_code >= 400:
        detail = ''
        if isinstance(body, dict):
            error = body.get('error') or body.get('message')
            detail = error.get('message', '') if isinstance(error, dict) else error
        hints = {401:'密钥无效或已过期',403:'账号或模型权限不足',404:'接口地址或模型不存在',429:'额度不足或请求过于频繁'}
        message = f'图片服务返回 HTTP {response.status_code}：{hints.get(response.status_code, "服务拒绝了请求")}'
        if detail:
            message += '。' + safe_detail(detail, cfg)
        raise ValueError(message)
    if not isinstance(body, dict):
        raise ValueError('图片服务没有返回 JSON 对象。请检查 API 基础地址，不能填写网站首页或控制台地址。')
    return body


def image_payload(body):
    data = body.get('data')
    if not isinstance(data, list) or not data or not isinstance(data[0], dict):
        keys = ', '.join(str(k)[:30] for k in body.keys())[:120]
        raise ValueError(f'图片服务返回格式不兼容：缺少 data[0]（顶层字段：{keys or "空"}）。需要同步图片编辑接口。')
    item = data[0]
    if isinstance(item.get('b64_json'), str) and item['b64_json']:
        value = item['b64_json']
        if value.startswith('data:') and ';base64,' in value:
            value = value.split(';base64,',1)[1]
        if len(value)>15_000_000:
            raise ValueError('图片服务返回的图片超过大小限制')
        try:
            return base64.b64decode(re.sub(r'\s+', '', value), validate=True)
        except (ValueError, binascii.Error):
            raise ValueError('图片服务返回了无效的 Base64 图片')
    if isinstance(item.get('url'), str):
        return item['url']
    raise ValueError('图片服务返回 data[0]，但没有 b64_json 或图片 url。')


async def download_result(url, cfg):
    parts = urlsplit(url)
    if parts.scheme not in ('http', 'https') or not parts.hostname or parts.username or parts.password:
        raise ValueError('图片服务返回了无效的下载地址')
    # Never forward the API key to image/CDN URLs, including redirects.
    async with image_client(cfg, timeout=60) as client:
        async with client.stream('GET', url, follow_redirects=True) as response:
            if response.status_code >= 400:
                raise ValueError(f'下载生成图片失败（HTTP {response.status_code}），请在服务后台检查图片。')
            chunks, total = [], 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > 10_000_000:
                    raise ValueError('生成图片超过10MB，无法导入')
                chunks.append(chunk)
            return b''.join(chunks)
