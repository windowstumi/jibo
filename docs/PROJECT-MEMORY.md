# 项目记忆

更新日期：2026-11-27。根据用户拉取后的代码及后续本地实验更新；后续以实际 Git 状态和代码为准。

## 当前基线

- 目录：`D:\jibo`。项目现名“极播”，Electron + Python/FastAPI + SQLite，`package.json` 版本 **0.7.0**（本地语音组件）。提交与远程同步状态以当前 Git 日志和状态为准。
- 本次核对时分支 `main`，HEAD 为 `d974ddecf3a9f5cb779265068faa76601194033f`，本地 `origin/main` 指向同一提交；开始更新记忆前工作区干净。本次没有重新 fetch 或推送。
- 历史包含 `a20a072`（项目内环境与可选 Live2D 工具）。此前对话中的“0.3.1 是当前版本”“环境提交尚未进入远程历史”已过时，不应继续作为当前状态。
- 新版操作说明以 `docs/jibo-0.6-guide.md` 为准；README 中 0.5、0.4、0.3 章节及调研文档是历史背景。

## 用户持续要求

- 二维动漫角色、商品知识与内容过滤、语音互动、礼物答谢、低配置客户端、迁移和打包。
- 嘴部自然开合即可，不要求音素级同步，不使用独立嘴贴图。
- 先检查本项目，再核对具体上游文件/API/运行入口。优先独立运行成熟工具或接口集成；只补足不适用部分，分别说明可直接接入、需适配、研究候选。
- 使用目标角色和实际语音验收，不能拿作者演示或静态夹具代替效果证明。分别核实代码、模型、示例素材、云服务的许可和商业分发条件。
- 不在记忆、源码、导出包中保存 API 密钥；付费生成结果不明时不自动重试。用户素材与当前验收状态不能从历史文档推定。

## 当前实现及入口

- **新版视频角色卡**：`character_pipeline.py` 的 `PRESETS` 定义五项基础素材：`idle` 自然待机、`talk` 平静说话、`thanks` 点头答谢、`greeting` 微笑招手、`present` 介绍手势；`happy` 开心说话可选，缺少时回退到 `talk`。
- **本地成片建卡与迁移**：`character_cards.py` 的 `create_local_card` / `assemble_local_card`、`validate_card`、`export_card` / `import_card`。现有入口只整理目标角色自己的成片，不会将参考演员替换成新角色。
- **云端制作**：`character_pipeline.py` 的 `analyze_character`、`submit_video` / `query_video`、`run_character`，组合视觉分析、标准图与万相动作视频；`quote` 提供预算。费用和成功率以实际服务为准，不能把历史预算当作固定价格或已验证结果。
- **媒体处理**：`transparent_video` 复用 FFmpeg 去绿/去溢色和 VP9 alpha；`probe_video` 使用 ffprobe。发布包未附带 FFmpeg/ffprobe，本地整理需要前者及后者，卡片导入需要 ffprobe 校验；已整理卡片的播放由 Chromium 完成。
- **HTTP 接口**：`character_routes.py::register_characters` 注册 `/api/characters`、`/from-existing`、`/import`、`/build`、`/{ident}/review`、`/{ident}/activate`、`/{ident}/package` 等，修改前阅读具体处理函数及校验。
- **播放器**：`static/character-player.js::CharacterPlayer`，最多两个原生 `HTMLVideoElement` 槽，约 250ms 交叉淡化；`beginSpeech` / `endSpeech` 随实际语音状态切换，单次手势结束后回说话或待机。嘴部活动来自原视频，无运行时嘴贴图，也没有任意动作/表情的独立自由组合。
- **工作台与业务**：`static/stage.js`、`static/app.js` 和 `app.py` 保留商品、过滤、优先队列、语音及透明播出声音归属；语音相关入口包括 `/api/scenes/test-voice` 与 `/api/player/tick`。应用新角色会停止旧播出，须重新彩排。
- **0.6.2 行为**：旧场景的程序化礼物/答谢点头已移除，礼物不再回退播放旧场景答谢短片。旧场景只做语音答谢；视频角色卡使用本卡 `thanks` 视频。保留旧用户素材，不自动删除。
- **旧路径和实验**：旧 2.5D 场景仍保留；`tools/avatar_pipeline/` 是独立、需角色校准的 PSD2Live 实验，未成为正式播放器，也不等于任意单图自动 Live2D 绑定。
- **可选 OBS**：`desktop/obs-client.cjs` 使用 `obs-websocket-js` 控制外部 OBS；客户端内角色预览不要求 OBS WebSocket。实际平台事件采集、OBS 现场推流仍须单独验收。

## 环境、构建与迁移

- `start.cmd` 自动准备项目内环境并启动；`setup.cmd` 只准备环境；`check.cmd` 执行环境、Python/Node 测试和真实桌面启动检查；`build.cmd` 打包便携 EXE，`-Target directory` 生成目录版。
- `runtime.versions.json`、依赖锁文件、`scripts/bootstrap.ps1` / `workspace.cjs` 管理 `.runtime/`、`.venv/`、`node_modules/`；一键入口面向 Windows x64，首次需联网。生成环境不提交 Git。
- 当前产物名配置为 `release/Jibo-Studio-0.6.2-win-x64.exe`；目录版为 `release/win-unpacked/极播.exe`。文件是否已经在本机生成必须另行检查，不能仅凭配置宣称存在。
- `desktop/platform.cjs::chooseDataRoot` 优先 `JIBO_DATA_DIR`，兼容 `YINGBO_DATA_DIR`；便携模式优先沿用旁边已有 `YingboData`，否则使用 `JiboData`。
- 角色 ZIP 不含密钥、商品或机器音色，导入需重新验收。完整项目携带当前应用卡与商品/规则等；角色包上限 300MB，完整项目上限 100MB。完整数据目录可能含密钥，迁移前先退出客户端。

## 验证证据与限制

- 本次只阅读代码和文档以更新记忆，**没有重跑测试、重新构建、调用收费生成或确认/应用任何角色**。
- 随后用户要求编译新版包：2026-11-26 在当前 Windows 10 x64 上执行 `build.cmd` 成功，生成 `release/Jibo-Studio-0.6.2-win-x64.exe` 和 `release/win-unpacked/极播.exe`。`check.cmd` 的 63 项 Python 测试、17 项 Node 测试与开发版启动检查均通过，目录版和便携 EXE 实际启动检查也通过；校验值与本次结果在忽略目录 `release/` 的 `.sha256` 和 `build-validation-0.6.2.json`。本机未找到可用于本轮回归的角色卡，未执行目标视频观感/动作回归，未调用收费生成；本轮打包结果不代表第二台机器或 OBS 现场验收。
- `docs/jibo-0.6-guide.md` 记录上轮已使用目标角色五段真实成片和 Windows 实际 TTS，验证开发/打包版的播放、动作、预览、导入导出、工作台与礼物、透明播出声音接管；这属于已有记录，不是本轮新实测。
- 上轮记录未完成新的付费云端完整制作、实际 OBS/抖音现场推流、第二台物理电脑及 macOS/Linux 验收。低配性能和持续运行仍需目标机器测量。
- 淡化不修复原视频变脸、肢体错误、嘴部活动不足或循环接缝；素材未包含的表情不能自动出现。不能将“有实现”表述为“所有目标素材已合格”。
- `docs/PORTABILITY-VALIDATION.md` 的 40 + 4 项测试和隔离目录重建/移动结果是 **0.3.1 历史验证**，不可用于宣称当前 0.6.2 的测试数量或重新换机成功。
- 当前角色是否已经验收、应用以及目标文件是否齐全，应读取本机实际状态后再判断，不能照搬使用说明里的历史机器状态。

## 后续接手

2026-11-27 后续用户明确授权：现有默认音色是本人录制，可以随软件商业分发；要求在项目中放许可文件，依赖安装时自动下载，配置放设置页，启动显示加载进度，默认NVIDIA，预留导入音色包。已实现0.7.0：`local_tts.py` 管理独立Python 3.11.9 / PyTorch 2.8.0+cu128 / v2官方推理、校验下载/续传、生命周期及音色包；`tools/local_tts/component.json` 和带哈希锁固定资源；`native_worker.py` 使用非阻塞Windows管道存活检测，避免阻塞stdin读取拖住DLL加载。`static/local-tts.js` 提供设置、真实下载进度、启动加载/预热窗口、试听、速度、下载源与音色ZIP导入；原外部9880/9881桥接不再是主流程。

默认音色包由 `scripts/build_voice_pack.py` 生成到 `build/local-tts/default-voice.zip`，随安装包分发，模型本身不进Git。第三方声明与MIT/Apache/GPL等文本在 `licenses/`，用户录音授权也保留在包内。NVIDIA组件安装到客户端数据目录的 `local-tts/`，与外部 `D:\GPT` 无关。正常启动不联网；公共模型、NLTK英文发音资源、GPU依赖在首次启用时下载并校验。预热包含USB等英文缩写。成功合成后删除已完成的大型安装归档，当前组件约9.7GiB；修复安装可能需重新下载。

0.7.0已编译 `release/Jibo-Studio-0.7.0-win-x64.exe`，约325.9MiB，含默认音色ZIP；独立音色包在 `release/Jibo-Default-Voice-v2.zip`。`check.cmd` 的70项Python、17项Node及开发桌面检查通过。使用真实默认音色完成开发版、目录版和最终便携EXE的加载窗口、预热、设置页真实播放、缓存与退出回收验证；最终EXE新生成7.46秒语音并开始播放耗时约3.47秒，缓存调用约0.004秒。自动验收脚本为 `scripts/smoke_local_tts.cjs --data <已准备组件的数据目录> [--exe ...]`；它会在指定数据目录保存本地语音选择，不能当作只读检查。仅实测当前Windows10/RTX5060机器，未验证第二台机器、低配或OBS现场推流。本机 `D:\jibo\data` 已设为集成本地音色；已有发布目录的个人设置保留，用户需在新版切换到本地NVIDIA并启用。原测试9880/9881服务已停止，不再让用户手动启动旧桥接脚本。使用说明见 `docs/local-tts-component.md`。

2026-11-27 用户搁置云语音，指定更新 `D:\GPT\GPT-SoVITS-v3lora-20250228` 并用现有音色试调用。原包无 Git，已在其 `updates/` 新增官方 `6d51ffceafbf240145619af4c92408a6e54b7924` 源码与隔离覆盖依赖，保留旧入口；复用原 PyTorch 2.8.0+cu128、已有 `cao` v2 权重与 4.5 秒参考音频，不是训练新模型或安装 v2Pro。官方 API 9880，极播兼容适配 9881，代码见 `tools/local_tts/`；整合包新增 `go-jibo-local-tts.cmd` 可启动两项服务。已通过隔离数据目录实际调用 `app.synthesize`，生成 `data/local-tts-check/jibo-cao.wav`；完整 8.02 秒音频调用耗时 3.548 秒，短欢迎语直调约 1.349 秒，首次初始化明显更慢，未验证 OBS 并行及客户最低配置。修复空密钥非法 Bearer 请求头，64 项 Python 测试通过。原 0.6.2 EXE 尚未重编，兼容 TTS 密钥可先填 `local` 占位；未修改用户已保存设置、调用收费服务或确认现有音色可商用。详见 `docs/local-tts-validation-2026-11-27.md`。

先查看 Git 状态、`AGENTS.md`、本文件和 `docs/jibo-0.6-guide.md`；按任务读取相关实现，再决定检查或修改范围。调研依据还可查 `docs/upstream-reuse-candidates-2026-11-26.md`、`docs/prerecorded-avatar-code-review-2026-11-26.md` 等，但候选状态须重新核对，不代表已接入。
