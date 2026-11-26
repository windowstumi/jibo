# 极播第三方组件与音色说明

更新日期：2026-11-27。此目录随桌面软件分发，组件自身的许可和权利声明仍然适用。

## GPT-SoVITS

- 来源：https://github.com/RVC-Boss/GPT-SoVITS
- 固定版本：`6d51ffceafbf240145619af4c92408a6e54b7924`
- 主仓库许可：MIT。完整声明见 `GPT-SoVITS-MIT.txt`，保留原版权声明。
- 极播复用上游推理代码，通过独立进程调用。为无需客户安装C++编译器，本地启动包装将 `jieba_fast` 的兼容接口映射到纯Python `jieba`；没有重写语音合成模型。
- 默认仅安装v2推理所需模型，不下载训练界面、其他版本模型或ASR工具。

## 录音与专属音色

本次默认音色所用录音及配套音色权重由用户提供。用户于2026-11-27明确声明：音色为本人录制，允许随极播商业软件分发。音色包保留该声明于 `VOICE-LICENSE.txt`。该授权不修改任何上游代码或公共模型的许可。

自行导入的音色包由导入者确认拥有使用及分发权利。音色包清单、模型、录音及哈希均随包保存；服务密钥不进入音色包。

## 公共模型及依赖

- 公共BERT/HuBERT模型使用 ModelScope `AI-ModelScope/GPT-SoVITS` 发布文件，其仓库元数据标记 MIT；来源、路径及逐文件SHA256固定在 `tools/local_tts/component.json`。原始模型来源包括HFL Chinese RoBERTa与TencentGameMate Chinese HuBERT；各自的模型声明及附随条件继续适用，不应将本文件视为新增授权。
- G2PW中文发音模型使用 `kamiorinn/g2pw` 发布的固定SHA256归档；上游：https://github.com/GitYCC/g2pW ，主仓库为Apache-2.0，完整声明见 `G2PW-LICENSE.txt`。归档附带的文件和许可信息保留。
- 独立Python环境、PyTorch、torchaudio、Transformers、PEFT、ONNX Runtime、jieba及其他依赖按其各自许可使用；安装时保留wheel中附带的许可证、版权声明与第三方说明，不从软件包中剥离这些文件。锁定依赖见 `tools/local_tts/requirements.lock.txt`。
- 商品中的英文缩写使用NLTK离线标注与发音资源：averaged_perceptron_tagger（MIT）及Carnegie Mellon Pronouncing Dictionary 0.6（原声明允许研究和商业使用）。固定来源、哈希及原版权/许可文字见 `NLTK-DATA-NOTICES.txt`；资源包附随文件原样保留。
- CUDA运行库来自所选官方PyTorch发行包，适用NVIDIA相应再分发条款；不包含显卡驱动安装程序。
- FFmpeg由 `imageio-ffmpeg==0.6.0` Windows wheel提供，以独立可执行程序处理音频。实测二进制是Gyan FFmpeg 7.1 essentials，启用了 `--enable-gpl --enable-version3`，适用GPLv3，完整文本见 `FFmpeg-GPL-3.0.txt`。封装自身为BSD-2-Clause，不替代二进制许可；版本及构建配置记录在组件目录的 `install.log`。对应源码与构建材料：https://github.com/imageio/imageio-ffmpeg 、https://www.gyan.dev/ffmpeg/builds/ 、https://ffmpeg.org/download.html 。客户端从上游wheel下载该独立程序，没有将其链接进极播后台。

本文件记录已采用组件，不授予超出各原许可范围的权利；升级或替换组件时应同步更新来源和声明。
