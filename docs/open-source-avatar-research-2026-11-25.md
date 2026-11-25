# 虚拟人直播开源方案调研

调研日期：2026-11-25。目标：用户提供图片定制形象，支持实时语音交互、商品讲解、抖音或 B 站直播。

本报告直接查阅了 GitHub 当前仓库、README、许可证和部分接口/配置文档。功能与性能数字来自各项目作者，不代表已在本机部署验收。没有下载运行模型，没有修改现有业务代码。

## 结论

有高度相似的开源项目，但本次没有确认一个项目能同时开箱即用地满足「任意图片生成高质量全身角色、自然实时对话、带货业务、抖音和 B 站稳定接入、商业分发」全部要求。

最值得优先验证的三个方向：

1. **OpenAvatarChat + LAM**：最贴近「单张图片 → 可驱动形象 → 语音对话」，适合优先验证形象生成能力。
2. **LiveTalking + 商品业务层**：最贴近「实时音视频数字人 → OBS/直播平台」，适合真人数字主播。其同作者 LiveStream 工具还提供循环话术、插入弹幕回复和知识库问答，但该工具仓库未发现明确许可证。
3. **Ikaros-521/AI-Vtuber**：最贴近「多直播平台互动主播整合」，适合参考弹幕、语音、模型和角色引擎的衔接；它本身不是单图角色生成模型。

现有映播项目已有商品、规则、事件队列和桌面工作台。建议保留这些资产，通过接口接入新的语音或角色引擎。先完成一种形象路线和一个直播平台的验收，再扩展其他路线。

## 主要候选

| 项目 | 适合解决的问题 | 图片生成形象 | 实时交互 / 直播 | 许可证与主要缺口 |
|---|---|---|---|---|
| [Ikaros-521/AI-Vtuber](https://github.com/Ikaros-521/AI-Vtuber) | 多平台 AI 主播整合 | 接入 Live2D、VTube Studio、数字人引擎；非自身单图生成 | README 列出 B站、抖音等平台，支持 LLM、TTS、拾音与多种角色输出 | GPL-3.0；分发衍生软件需评估源码提供义务；部分平台依赖外部采集工具，实际连接需验证 |
| [lipku/LiveTalking](https://github.com/lipku/LiveTalking) | 实时数字人渲染与音视频输出 | 自定义角色；当前 Avatar 页面以上传视频生成角色为主要流程，不能直接等同单图自动建模 | WebRTC、RTMP、虚拟摄像头；可打断；提供 HTTP API | 框架 Apache-2.0，但模型另算；README 另声明发布视频需带水印和标识；不要将商业版功能全部视为开源版功能 |
| [HumanAIGC-Engineering/OpenAvatarChat](https://github.com/HumanAIGC-Engineering/OpenAvatarChat) | 模块化实时语音数字人 | 接入 LAM 后可实现单图生成的头像交互；另有 LiteAvatar、MuseTalk、FlashHead | ASR / LLM / TTS / Avatar 模块；0.6.0 文档支持手动和双工打断 | Apache-2.0；具体模型、资源另查；商品知识库和平台弹幕需补接 |
| [aigc3d/LAM](https://github.com/aigc3d/LAM) | 单张图片生成可动画化的 3D 高斯头部头像 | 是，核心是头部头像，并非完整全身骨骼角色 | 配合 Audio2Expression、WebGL 渲染、OpenAvatarChat 对话 | Apache-2.0；生成、导出、运行时渲染是不同环节；导出文档还要求 Blender、FBX SDK 等依赖 |
| [Open-LLM-VTuber](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber) | 二次元 Live2D 语音助手 | 导入已制作的 Live2D 模型，不能把任意 PNG 自动变成 Live2D | 语音对话、打断、表情、透明桌面模式，支持 Windows/macOS/Linux | 主代码 MIT，Live2D 示例模型另有许可；商业模型和 SDK 需另核；商品和平台接入需开发 |
| [PeterH0323/Streamer-Sales](https://github.com/PeterH0323/Streamer-Sales) | 商品文案、说明书问答、卖货业务 | 包含数字人视频生成流程，不是完整单图实时直播产品 | RAG、ASR、TTS、商品讲解；不能仅凭这些功能判定具备低延迟直播链路 | AGPL-3.0；网络服务部署也涉及对应源码义务；本地完整模型栈较重 |
| [honwee/mynah](https://github.com/honwee/mynah) | 一体化实时数字人服务端 | 提供 FlashHead 等引擎、头像相关功能 | WebRTC、打断、ASR、知识库、管理控制台 | Apache-2.0；Go 核心 + Python workers，集成部署比本项目重；社区规模较小，需额外验证成熟度 |

### 1. 最像完整 AI 主播：AI-Vtuber

README 明确列出 Bilibili、抖音、快手、视频号等平台，支持多种 LLM、语音识别、TTS、Live2D、VTube Studio、DH_live、MuseTalk 等组件。本地语音和直播弹幕可进入交互链路。

适合研究「观众事件 → 回答 → 配音 → 角色输出」的编排。应注意：各平台的接入机制不同，部分依赖外部监听助手，平台列表不等于每个平台都由项目直接稳定接入。GPL-3.0 不禁止商业使用，但不应直接复制代码到计划闭源分发的产品而忽略许可义务。

### 2. 最像实时真人数字主播底座：LiveTalking

支持 ernerf、MuseTalk、Wav2Lip、Ultralight-Digital-Human 等模型，提供 WebRTC、RTMP、虚拟摄像头输出，支持语音打断、全身视频拼接及自定义闲置动作视频。

API 可通过 `/human` 提交文字，选择直接播报或 LLM 对话；`/humanaudio` 接收音频文件。现有映播可继续负责商品问答和内容规则，将审核后的结果交给该引擎。

作者公布的参考性能：MuseTalk 在 RTX 3080Ti / 3090 / 4090 上分别约 42 / 45 / 72 FPS。它们是特定配置下的推理数据，不能据此保证同时运行 ASR、LLM、TTS 和 OBS 时的性能或首句延迟。作者同时提醒 `inferfps` 与最终 `finalfps` 均需达标。

同作者的 [LiveStream](https://github.com/lipku/LiveStream) 明确支持：循环播放话术、插入弹幕回复、根据知识库回答问题，通过 OBS 或直播伴侣采集画面。它是本次发现业务形态最接近的项目之一。但调研时其仓库根目录没有 LICENSE，GitHub 仓库元数据也未识别许可证，不能因 LiveTalking 是 Apache-2.0 就推定它同样授权。优先作为设计参考。

### 3. 最贴近单张图片要求：OpenAvatarChat + LAM

LAM 用一张图片生成可驱动的 3D 高斯头部头像；Audio2Expression 根据音频生成表情；WebGL 负责渲染。官方明确提供导出到 OpenAvatarChat 的说明，并有 `chat_with_lam.yaml` 预置模式。

这是现有 2.5D 网格角色之外值得优先做样例比较的路线。其“3D”主要针对头部头像；不能承诺自动得到完整 Live2D 拆层、全身骨骼、服装物理、拿取商品等动作。对于二次元全身立绘，需要单独验证输入适配，不应直接套用真人头像效果承诺。

LAM 文档公布的 1.4 秒重建、移动设备渲染帧率，属于指定模型和设备的结果；重建耗时、实时渲染帧率与整条对话延迟是三种不同指标。

## 可复用的底层模型和补充项目

| 项目 | 能力 | 对本项目的价值与限制 |
|---|---|---|
| [MuseTalk](https://github.com/TMElyralab/MuseTalk) | 音频驱动口型；支持图片/视频输入和角色预处理 | 可替换当前只按音量混合开合的嘴型。不是完整的 ASR、商品问答或平台直播系统。主代码 MIT，作者允许已发布模型商用，但测试素材仅供非商业研究，第三方模型分别受许可约束 |
| [SoulX-FlashHead](https://github.com/Soul-AILab/SoulX-FlashHead) | 单图 + 音频，生成流式说话头 | 已被 OpenAvatarChat 接入。更值得用于自然头部运动实验；算力较重。官方称 Lite 在 RTX 4090 达 96 FPS，Pro 单张 4090 约 10.8 FPS，实时 Pro 需双 RTX 5090；均未在本机验证 |
| [LivePortrait](https://github.com/KlingAIResearch/LivePortrait) | 图片/视频的肖像动画、表情重定向 | 可用于制作待机或动作素材；原项目主要使用驱动视频/运动信息，不是完整音频对话系统。LICENSE 明确提醒默认 InsightFace 检测模型不能直接商用，需要替换 |
| [DH_live](https://github.com/kleinlee/DH_live) | 轻量视频数字人、浏览器端推理、VAD-ASR-LLM-TTS 链路 | 更接近现有 Electron/WebGL 运行方式。主要用人物视频准备资产，非单图自动全身建模。README 写 MIT，但另有网页角色授权及去 Logo 说明，需明确代码和资产授权边界 |
| [MatesX](https://github.com/kleinlee/MatesX) | DH_live 作者的多端对话应用，含 Electron/WebGL | 值得参考桌面形态。但 README 明确不提供底层算法实现，定制头像依赖其平台/API，不应归类成完整自主的本地头像生成系统 |
| [Duix-Avatar，原 HeyGem.ai](https://github.com/duixcom/Duix-Avatar) | 真人形象克隆、配音、离线口播视频制作 | README 明确说是非实时视频合成，因此不作为实时交互直播首选。当前是自定义社区许可，不是普通 MIT/Apache 授权 |

## 许可证与维护状态：已发现的具体问题

1. **LiveTalking 的许可不覆盖所有模型。** [原始 Wav2Lip README](https://github.com/Rudrabha/Wav2Lip) 明确限制开源版本用于个人、研究、非商业用途。正式带货不能仅凭框架 Apache-2.0 就直接采用该权重。MuseTalk 等路线也要核对依赖、素材和实际使用的模型版本。LiveTalking README 还有发布视频带水印/标识的声明，商用前需要澄清与开源许可的关系。
2. **LivePortrait 默认检测模型有明确商业限制。** [LICENSE](https://github.com/KlingAIResearch/LivePortrait/blob/main/LICENSE) 要求商业使用时移除并替换 InsightFace 检测模型。
3. **Duix 的 README 和 LICENSE 门槛存在冲突。** README 描述的是 10 万用户或年营收 1000 万美元条件；本次读取的 [LICENSE](https://github.com/duixcom/Duix-Avatar/blob/main/LICENSE) 第 2 节写的是超过 1000 月活需申请商业许可，并有品牌展示要求。应以待采用版本的完整许可和书面授权为准，不能据营销介绍判断。
4. **Live2D 示例模型不随主代码一并获得 MIT 授权。** 见 Open-LLM-VTuber 的 [LICENSE](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/blob/main/LICENSE) 和 [LICENSE-Live2D.md](https://github.com/Open-LLM-VTuber/Open-LLM-VTuber/blob/main/LICENSE-Live2D.md)。
5. **部分 B站接入依赖已停止维护。** [Nemo2011/bilibili-api](https://github.com/Nemo2011/bilibili-api) 当前 README 宣布停止维护和永久关停，并展示日期为 2026-07-06 的告知函。[digital-human-livestream](https://github.com/l11223/digital-human-livestream) 虽列出 B站弹幕、DeepSeek、过滤、后台等完整功能，但依赖这个库，不能直接当成可靠的平台接入底座。技术方案应优先核对 B站开放平台可用权限，并把事件采集器做成可替换模块。
6. **抖音采集应单独验收。** LiveStream 推荐 [DouyinBarrageGrab](https://github.com/ape-byte/DouyinBarrageGrab)，其 README 描述通过代理抓包或相关监听机制向 WebSocket 转发弹幕，且说明 GitHub 更新可能落后于 Gitee。它不是抖音官方开放 API，也不是头像生成工具。需要在实际授权直播间验证当前可用性、部署方式和维护风险。
7. **FlashHead Lite 的依赖许可需单独确认。** [Mynah 的依赖许可清单](https://github.com/honwee/mynah/blob/main/LICENSING.md) 特别指出 LTX-Video VAE 的条款需要核验；不能只看 FlashHead 仓库的 Apache-2.0。

## 与当前映播项目对照

根据 README、ACCEPTANCE.md、app.py、package.json 和 requirements.txt：

| 模块 | 当前实现 | 下一步可借鉴方案 |
|---|---|---|
| 桌面客户端 | Electron + FastAPI + SQLite，已具备工作台和项目迁移 | 保留现有外壳，通过本地服务接口接入推理引擎 |
| 图片角色 | 4 次图片生成构建 2.5D 网格场景；中性/说话/闭眼纹理混合 | 真人头像先试 LAM；更自然流式人像可比较 FlashHead；二次元使用专门制作的 Live2D 模型 |
| 嘴型 | 音量驱动中性/说话表情混合，非音素识别 | 比较 MuseTalk、LAM Audio2Expression 的真实语音同步效果 |
| 语音交互 | 有 TTS 和文本商品问答；未看到完整麦克风 ASR/VAD/回声处理/双工打断链路 | 参考 OpenAvatarChat 或 Open-LLM-VTuber 的语音链路 |
| 带货业务 | 商品资料、FAQ、生成讲解稿、依据检索、内容过滤、播放队列 | 保留业务层；参考 Streamer-Sales 的资料整理，但不必为了接入而自训卖货模型 |
| 直播输出 | 本地浏览器源与 OBS；没有直接替用户启动平台直播 | 继续用 OBS；真人渲染可交给 LiveTalking，通过 WebRTC/虚拟摄像头输出 |
| 直播事件 | 有带鉴权的 `/api/events`；未包含平台采集器 | 将平台事件归一化后送入既有接口，增加重连、去重、限流、礼物合并和来源状态 |

## 建议的验证顺序

1. 用同一张有代表性的用户图片，比较当前角色、LAM、FlashHead 的外观保持、嘴型、待机动作与部署要求。二次元全身图另外作为一组样本，不混同真人头像验收。
2. 先验证单机「麦克风 → VAD/ASR → 商品问答 → TTS → 角色」；测首句延迟、打断停止时间、回声误识别与连续运行稳定性。
3. 用既有商品知识库验证价格、规格、库存和售后答复，再验证主动讲解被弹幕打断后的恢复策略。
4. 用一个实际直播间验证「平台事件 → `/api/events` → 回答 → OBS」，明确消息去重、断线恢复和高峰积压处理。
5. 选定版本后再核验模型和素材许可、硬件占用，并测试持续运行与分发安装。

建议首先做 **OpenAvatarChat + LAM 的小范围效果验证**，它直接回答本需求最关键的「用户只给一张图片能做到什么程度」。若主目标改为真人视频主播且可提供人物视频，则优先验证 **LiveTalking + MuseTalk**；若主目标是二次元全身主播，则优先验证 **已制作 Live2D 模型 + Open-LLM-VTuber**。平台互动编排参考 **AI-Vtuber**，商品层保留现有映播实现。
