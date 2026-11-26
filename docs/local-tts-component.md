# 极播0.7：本地克隆语音组件

## 客户使用

打开「接入设置 → 语音合成」，选择「本地克隆音色 · NVIDIA」，点击「安装并启用」。无需安装Python、PyTorch或手动启动外部项目。首次下载依赖与公共模型，网络中断后可再次点击继续；文件按固定SHA256校验。安装前请保留至少15GB空间，并安装兼容CUDA 12.8的NVIDIA驱动。

已有Windows系统语音或外部接口配置会保留，首次选择本地模式才安装组件。启动进度显示实际下载字节数；依赖安装、模型加载和预热阶段使用不定进度条，不显示虚构百分比。加载完成后自动关闭提示。可以后台继续处理商品等其他工作，语音未就绪时不能试听。

安装完成后勾选「打开客户端时自动加载并预热」，以后启动软件会自动准备音色。已安装的组件正常启动不再下载依赖。语速范围0.5至2；下载源可选择清华或官方PyPI，大型PyTorch文件优先使用官方源并有校验相同的镜像后备。

组件位于客户端数据目录的 `local-tts/`，不依赖开发机器的 `D:\GPT`。`install.log` 记录安装，`service.log` 记录推理服务。遇到错误在设置页重新安装/加载，按日志检查网络或驱动；不会静默切到CPU。

英文缩写所需的NLTK资源在安装阶段一并下载校验，预热包含USB示例，避免直播中首次遇到常见英文商品词时临时联网或额外初始化。

## 安装与体积

主包仅携带客户端、推理启动与安装代码、许可证和本次授权的默认音色ZIP。Python/NVIDIA运行库、BERT/HuBERT及中文发音模型在用户启用时下载；不附带Gradio、训练界面、ASR、其他版本语音模型或CUDA编译器。

PyTorch官方Windows CUDA 12.8 wheel本身约3.2GiB，无法仅靠前端整合消除这部分依赖。安装后还会占用模型和解压空间。中断的下载缓存用于恢复；实际合成并预热成功后自动清理已完成的大型PyTorch与G2PW安装归档，节省约3.8GiB，维修重装可能需要重新下载。主EXE大小与安装后组件占用是不同指标。安装完成后离线播放与合成均可使用，图片/视频生成不属于本组件。

组件复用固定GPT-SoVITS上游API和模型，不重写语音算法。为无需C++编译器，以API兼容的纯Python `jieba` 代替 `jieba_fast` 分词；FFmpeg使用 `imageio-ffmpeg` wheel附带的独立可执行程序。中文发音模型通过CPU ONNX Runtime处理，主要语音模型在NVIDIA GPU推理。

## 音色包

设置页「导入音色包」支持独立ZIP。包内必须只有以下文件：

```text
voice.json
VOICE-LICENSE.txt
gpt.ckpt
sovits.pth
reference.wav
```

`voice.json` 声明 `schema:1`、`version:"v2"`、名称、准确的参考录音文字，以及 `gpt` / `sovits` / `reference` 的 `file` 和 `sha256`。参考WAV须为3至10秒PCM音频。导入分配新ID，不覆盖其他音色；选择后点击「加载所选音色」，会释放原模型再加载新模型。

当前只承诺GPT-SoVITS v2模型对，默认中文；其他版本需要对应模型与资源适配。一个模型对应一对GPT/SoVITS权重，不能将任意两个文件混用。导入者须信任音色包来源；上游模型加载器使用PyTorch checkpoint，哈希仅确认文件未变化，不代表未知checkpoint没有代码执行风险。

音色独立存放，不将服务密钥写入包。现有完整项目导出不自动包含整套GPU环境或音色库；跨机可重新安装组件、导入相同音色包，再重新选择音色。完整数据目录迁移后如虚拟环境路径失效，组件会重建环境。

## 构建默认音色与发布包

用户提供的录音及音色权重允许随软件商业分发；该声明保留在包内。准备默认包：

```powershell
.\.venv\Scripts\python.exe scripts/build_voice_pack.py --gpt "path\voice.ckpt" --sovits "path\voice.pth" --reference "path\reference.wav" --text "参考录音实际说出的文字"
.\build.cmd
```

音色ZIP输出至 `build/local-tts/default-voice.zip`，桌面构建将其复制到资源目录。权重不提交Git；在其他构建机器上需准备同一授权音色包。没有默认包仍可编译客户端，但客户首次需导入自己的音色包后才能使用本地语音。不要把整个旧整合包或其中的个人配置放进安装包。

第三方声明在 [licenses/THIRD-PARTY-NOTICES.md](../licenses/THIRD-PARTY-NOTICES.md)，代码、模型、运行库和录音的条件分别保留。本组件不代表所有客户机器均已通过低延迟验收，最低配置及OBS并行性能需要实际目标机器测试。
