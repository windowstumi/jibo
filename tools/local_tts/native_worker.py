"""Launch unmodified upstream inference in the optional NVIDIA environment."""
import argparse
import os
from pathlib import Path
import runpy
import sys
import threading
import faulthandler
import time


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--port', required=True)
    args = parser.parse_args()
    # The pipe belongs to jibo. Release the GPU even if its parent crashes.
    def parent_watch():
        if os.name == 'nt':
            # A blocking CRT stdin read can hold the Windows CRT lock while
            # PyTorch loads DLLs. Peek at pipe liveness instead of reading it.
            import ctypes
            from ctypes import wintypes
            import msvcrt
            kernel = ctypes.WinDLL('kernel32', use_last_error=True)
            peek = kernel.PeekNamedPipe
            peek.argtypes = [wintypes.HANDLE, ctypes.c_void_p, wintypes.DWORD,
                             ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p]
            peek.restype = wintypes.BOOL
            handle = msvcrt.get_osfhandle(sys.stdin.fileno())
            while True:
                if not peek(handle, None, 0, None, None, None):
                    if ctypes.get_last_error() in (6, 109, 232):
                        os._exit(0)
                    return
                time.sleep(.5)
        else:
            sys.stdin.buffer.read()
            os._exit(0)
    threading.Thread(target=parent_watch, daemon=True).start()
    faulthandler.enable()
    engine = args.engine.resolve()
    os.chdir(engine)
    sys.path[:0] = [str(engine), str(engine / 'GPT_SoVITS')]
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.environ['TOKENIZERS_PARALLELISM'] = 'false'
    os.environ['NLTK_DATA'] = str(engine / 'runtime/nltk_data')
    print('JIBO_PHASE: 正在加载 GPU 运行库', flush=True)
    import torch
    if not torch.cuda.is_available():
        raise RuntimeError('未检测到可用的 NVIDIA CUDA，请更新显卡驱动。')
    torch.set_num_threads(4)
    torch.set_num_interop_threads(2)
    print('JIBO_PHASE: 正在准备中文文本处理', flush=True)
    # jieba_fast ships no Windows CPython 3.11 wheel. Its public segmentation
    # interface is compatible with upstream jieba; avoid a customer C++ compiler.
    import jieba
    import jieba.posseg
    sys.modules['jieba_fast'] = jieba
    sys.modules['jieba_fast.posseg'] = jieba.posseg
    import imageio_ffmpeg
    import tools.portable_runtime as portable
    portable.FFMPEG_EXE = Path(imageio_ffmpeg.get_ffmpeg_exe())
    portable.FFPROBE_EXE = portable.FFMPEG_EXE
    print('JIBO_PHASE: 正在载入语音模型', flush=True)
    sys.argv = ['api_v2.py', '-a', '127.0.0.1', '-p', args.port,
                '-c', str(args.config.resolve())]
    runpy.run_path(str(engine / 'api_v2.py'), run_name='__main__')


if __name__ == '__main__':
    main()
