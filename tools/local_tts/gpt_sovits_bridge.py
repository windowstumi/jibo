"""Adapt the official local GPT-SoVITS /tts API to jibo's WAV speech endpoint.

Only request/response translation lives here; synthesis runs in upstream GPT-SoVITS.
Reference recordings and their transcripts are configured outside source control.
"""
import argparse
import io
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import wave


def load_config(path):
    config = json.loads(path.read_text(encoding="utf-8"))
    endpoint = urllib.parse.urlsplit(config["upstream"])
    if endpoint.scheme != "http" or endpoint.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise ValueError("The upstream must be a local HTTP service.")
    if endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
        raise ValueError("Unexpected credentials or query in the upstream URL.")
    for profile in config["voices"].values():
        reference = Path(profile["ref_audio_path"])
        if not reference.is_absolute():
            reference = path.parent / reference
        if not reference.is_file():
            raise ValueError(f"Reference recording not found: {reference}")
        profile["ref_audio_path"] = str(reference.resolve())
        if not profile.get("prompt_text"):
            raise ValueError("Each voice needs an accurate reference transcript.")
    return config


def upstream_request(body, config):
    text = body.get("input")
    if not isinstance(text, str) or not text.strip() or len(text) > 2000:
        raise ValueError("input must contain 1-2000 characters.")
    if body.get("model") != "gpt-sovits":
        raise ValueError("model must be gpt-sovits.")
    voice = body.get("voice")
    if not isinstance(voice, str) or voice not in config["voices"]:
        raise ValueError("Unknown configured voice.")
    if body.get("response_format", "wav") != "wav":
        raise ValueError("Only complete PCM WAV output is supported.")
    profile = config["voices"][voice]
    return {
        "text": text,
        "text_lang": profile.get("text_lang", "zh"),
        "ref_audio_path": profile["ref_audio_path"],
        "prompt_text": profile["prompt_text"],
        "prompt_lang": profile.get("prompt_lang", "zh"),
        "text_split_method": "cut5",
        "batch_size": 1,
        "media_type": "wav",
        "streaming_mode": False,
        "use_cuda_graph": True,
        "use_flash_attention": False,
        "seed": 42,
    }


def make_handler(config):
    lock = threading.Lock()
    # Local requests must not be sent through the machine's VPN HTTP proxy.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    class Handler(BaseHTTPRequestHandler):
        def send_body(self, status, body, content_type="application/json", **headers):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            for name, value in headers.items():
                self.send_header(name, str(value))
            self.end_headers()
            self.wfile.write(body)

        def error(self, status, message):
            self.send_body(status, json.dumps({"error": message}).encode())

        def do_GET(self):
            if self.path == "/health":
                self.send_body(200, json.dumps({"adapter_ready": True, "upstream": config["upstream"],
                                               "voices": list(config["voices"]),
                                               "upstream_checked": False}).encode())
            else:
                self.error(404, "Not found")

        def do_POST(self):
            if self.path != "/v1/audio/speech":
                self.error(404, "Not found")
                return
            try:
                size = int(self.headers.get("Content-Length", "0"))
                if not 0 < size <= 32768:
                    raise ValueError("Invalid request size.")
                body = json.loads(self.rfile.read(size))
                if not isinstance(body, dict):
                    raise ValueError("A JSON object is required.")
                payload = upstream_request(body, config)
            except (ValueError, TypeError) as error:
                self.error(400, str(error))
                return
            if not lock.acquire(blocking=False):
                self.error(429, "The single-voice worker is busy; requests are not retried.")
                return
            started = time.perf_counter()
            try:
                request = urllib.request.Request(config["upstream"].rstrip("/") + "/tts",
                    data=json.dumps(payload, ensure_ascii=False).encode(),
                    headers={"Content-Type": "application/json"})
                with opener.open(request, timeout=120) as response:
                    raw = response.read()
                with wave.open(io.BytesIO(raw)) as audio:
                    if audio.getnframes() <= 0 or audio.getcomptype() != "NONE":
                        raise ValueError("The upstream returned an invalid PCM WAV.")
                self.send_body(200, raw, "audio/wav",
                               **{"X-Synthesis-Seconds": f"{time.perf_counter()-started:.3f}"})
            except urllib.error.HTTPError as error:
                self.error(502, f"GPT-SoVITS returned HTTP {error.code}; check its local console.")
            except (OSError, ValueError, EOFError, wave.Error):
                self.error(502, "GPT-SoVITS failed or returned invalid audio; check its local console.")
            finally:
                lock.release()

        def log_message(self, fmt, *args):
            # Log request paths/status only, never submitted speech or credentials.
            print(fmt % args, flush=True)

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--port", type=int, default=9881)
    args = parser.parse_args()
    config = load_config(args.config.resolve())
    with ThreadingHTTPServer(("127.0.0.1", args.port), make_handler(config)) as server:
        server.daemon_threads = True
        print(f"Local GPT-SoVITS adapter: http://127.0.0.1:{args.port}/v1", flush=True)
        server.serve_forever()


if __name__ == "__main__":
    main()
