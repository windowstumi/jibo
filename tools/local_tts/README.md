# Local GPT-SoVITS connection

**jibo 0.7 uses the managed component in Settings by default when local voice
is selected.** See [the component guide](../../docs/local-tts-component.md).
`component.json`, `requirements.lock.txt` and `native_worker.py` belong to that
managed path. The standalone bridge described below is the earlier optional
external-service adapter and is no longer required by the integrated mode.

This is a small adapter for the upstream `api_v2.py` `/tts` endpoint. It does
not implement or bundle a speech model, training code, weights, or recordings.
Run GPT-SoVITS separately with a compatible model pair already loaded.

1. Copy `config.example.json` into an ignored directory such as
   `data/local-tts/bridge.json`. Set a voice name, an existing reference WAV and
   its exact transcript. Relative WAV paths are relative to the JSON file.
2. Start the official GPT-SoVITS API on `127.0.0.1:9880`.
3. From the jibo repository, run:

   ```powershell
   .\.venv\Scripts\python.exe tools/local_tts/gpt_sovits_bridge.py --config data/local-tts/bridge.json
   ```

4. In jibo's compatible TTS settings, enter base URL
   `http://127.0.0.1:9881/v1`, model `gpt-sovits`, voice matching the JSON key,
   and an empty API key. The adapter listens on loopback only. Older desktop
   builds (including the earlier 0.6.2 EXE) send an invalid empty Bearer header;
   enter `local` as a placeholder key in those builds. Updated source omits
   authentication when the key is empty. The placeholder is not a cloud key.

`GET /health` reports adapter configuration only, not upstream readiness.
The adapter returns complete PCM WAV files, matching the existing
`app.synthesize` contract. It does not enable streaming playback or select
different weight pairs per request. Multiple references use the currently
loaded upstream weights; change those in upstream before switching models.
It accepts one synthesis at a time and returns 429 when busy, without retries.

Keep reference samples, profiles and generated audio outside Git. On 2026-11-27
the user confirmed that the supplied default recording is their own and may be
commercially distributed; its voice package retains that declaration. Other
imported recordings/weights retain their respective conditions. The upstream
MIT code license does not establish rights to arbitrary voices. This legacy
adapter is not included in the desktop application's automatic startup.
