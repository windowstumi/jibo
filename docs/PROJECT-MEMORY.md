# 项目记忆

更新日期：2026-11-27。根据用户拉取后的代码及后续本地实验更新；后续以实际 Git 状态和代码为准。

## 0.9.0 Git同步授权与范围

2026-11-27用户明确要求将本地项目提交并上传远程仓库。目标为现有origin/main（https://github.com/windowstumi/jibo.git），本次fetch后确认远程与本地提交基线385c524一致，未产生分叉。发布范围包含0.7之后累计的旧模块清理、语音安装修复、聊天/角色设定、互动语音动画衔接与0.9界面重整，以及对应文档与测试。

提交前扫描128个候选源码/文档文件：未发现疑似真实密钥、模型/录音/数据库/EXE等文件，也无超过1MB文件。现有忽略规则确认排除release、用户数据、音色ZIP、模型权重、运行环境和test-output；本次只同步代码和文档，不创建GitHub Release、不上传安装包或用户素材。功能验证沿用本轮已通过的76项Python、16项Node及0.9打包目录版真实角色回归，详见下方记录。最终提交与推送状态以Git日志和远程结果为准。

## 0.9.0 工作空间UI与上手路径重整

2026-11-27用户要求科技感UI、功能配置归整和明确首次使用步骤。此轮修改客户端工作台界面，不重新制作角色/模型，不改变播出逻辑与素材：

- static/style.css统一蓝黑底/青蓝强调色、较高对比文字、状态文字+颜色、原生表单、侧栏创作/管理分组和响应式布局；Electron nativeTheme只设置本应用深色、启动底色一致。不新增UI框架/字体/在线视觉资源或GPU开销。
- 新增默认home页「开始使用」：角色→声音→真实商品→互动守则四步，按现有状态推荐下一步；示例sample-cup不标为真实商品完成，系统/兼容语音明确是已选/待试听，本地语音仅当所选voice_id实际ready时完成。状态不变时不重建引导按钮，避免轮询丢失键盘焦点。static/workspace-ui.js负责原生分类/路由/引导，沿用现有API与表单。
- 原五页改为工作台/角色中心/知识库/互动与守则/设置中心；设置中心六组：声音、AI、图片、角色生成、直播接入、数据迁移。将原角色页的视觉/视频/预算/代理/动作库/OBS配置移到设置中心，保留同一控件ID和原表单，没有复制第二份密钥配置。按类别显示保存表单，切换不丢未保存输入；键盘方向键及Home/End可选分类。旧生成按钮跳转新分类，隐藏字段的浏览器校验能跳回相应分类。角色页保留角色设定/语音动作预览/应用导出；本地建卡材料折叠，付费新图制作独立折叠入口；移除工作台重复的制作广告说明。
- 项目导入导出/数据目录统一在设置中心数据分类，角色ZIP继续在角色中心、音色ZIP在声音分类。无音色时下拉改为“尚未导入音色包”，说明先导入再加载，避免误认为安装组件会自带音色。透明播出内容本身不套用管理UI主题。
- desktop/workspace-check.cjs在真实Electron验证首页/下一步、六类路由、无重复ID和嵌套表单、实际服务及制作配置保存/恢复、分类间未保存输入保持、空数据/示例/错误音色的准备状态。smoke_desktop纳入检查与常规/984px窗口各页面无横向溢出，捕获home/voice/generation/compact截图。开发版空数据最新版报告yingbo-smoke-FyYPlq，settingsSaved=true；实际角色+SAPI声音回归报告yingbo-smoke-qMrMsZ，迁移、答谢/介绍/招手、透明声音归属通过。76项Python、16项Node回归通过；未调用云端生成或新语音模型、未改用户真实配置。
- 新使用路线docs/jibo-0.9-guide.md，README版本0.9.0，历史0.8文档加新版入口说明。未自动Git提交/推送，不关闭用户旧版，原YingboData保留，语音环境清单未改变。
- 打包目录版0.9.0已通过新UI和实际角色完整回归，报告yingbo-smoke-7htATk（settingsSaved、darkTheme、全部984px页面fits、实际SAPI声音、角色/设定ZIP迁移、工作台动作和礼物视频及透明窗口声音归属通过）。已核对打包static中的index/style/workspace-ui/app/character-workshop/local-tts与源码SHA256一致；脱敏报告及home/voice/generation/studio截图复制到忽略的test-output/ui-redesign。管理主题没有改变角色原本的背景与播出画面。
- 已生成release/Jibo-Studio-0.9.0-win-x64.exe，118568438字节。用户退出旧客户端后在原release目录打开新版即可沿用YingboData；本轮未自动替用户启动新版或提交Git。

## 0.8.4 互动播出与语气动作一致性

2026-11-27用户反馈互动有记录但无字幕语音动画。只读本机实际状态确认active=false、current=null、queue_length=2，两条聊天均ready；实验室原来只入队，没有启动播出。新版实验室表单在停止状态自动开启interactions_only模式（无需先合成商品讲解，商品可不填，仍需已验收角色卡），再启用声音/发送事件。正常已播出时不重启会话；平台/api/events不自动启动播出。

- app.Start增加interactions_only，runtime公开mode；实验室自动启动互动预览，旧未播任务在新会话清理。无商品时仍可做聊天。原商品彩排保持必选有效商品和原有讲解流程。
- interaction.answer_chat在原有第二次审查请求中按最终回复语义生成白名单emotion/gesture，不新增模型请求。内部返回4元组（答复、证据、原因、delivery）；失败第4项为空字典。speech_delivery生成tone、emotion(talk/happy)、gesture(None/thanks/greeting/present)，未开启聊天用本地简短语义规则，礼物固定thanks；sad/serious/curious不套开心手势。任务携带自己的文字/音频/动画元数据；没有新的疑惑/生气/难过视频，使用talk回退，不能宣称已有这些表情素材或声学情绪控制。
- 继续复用CharacterPlayer与Chromium原生媒体/250ms淡化，不引入嘴贴图。stage先缓冲音频，再进入动作并播放；字幕在audio.play成功后显示。音频结束立即隐藏字幕，endSpeech等待未完成手势自然结束、淡回idle，完成后再确认当前任务，避免旧动作串到下一段。停止/替换取消旧异步回调；服务端current取消且没有新任务时停止旧声音。活跃同角色的普通设置消息不再重载画面、重复播放当前语音。
- 可选OBS原生场景适配接收相同的emotion/gesture，保留布尔IPC兼容；手势结束按当前说话情绪回退。此路径有单元回归，本轮未连接真实OBS现场验证。
- 新增stage媒体就绪/字幕时机/取消回归，更新短语音等手势的播放器回归、无商品互动模式及审核动作元数据检查。76项Python、16项Node测试通过。测试新增角色目录已在用例结束清理，避免残留测试角色影响后续项目导出检索。
- 新增显式真实验收脚本scripts/smoke_interaction.py和desktop/interaction-check.cjs（JIBO_SMOKE_INTERACTION）；只读用户配置，使用隔离角色副本与临时数据库、已有GPT-SoVITS桥接器调用已加载本地音色，结束清理带密钥的临时数据库。未改原配置、音色或角色。实际端到端通过：真实云端回复happy/greeting，角色实际greeting，17.7秒真实语音和字幕一致；礼物短音频1.22秒后字幕隐藏且仍等本次thanks视频结束，再播平静talk；最后idle且无商品讲解循环。证据test-output/interaction-live/report.json及三个WAV，确认private-*临时目录已清理。没有付费重试，没有新视频生成、训练或重装语音环境。
- 说明与复用接口/验证边界见docs/interaction-playback.md。版本0.8.4，未自动Git提交或推送，用户仍需退出旧版后打开新版。
- 已生成release/Jibo-Studio-0.8.4-win-x64.exe，118559392字节；打包目录版实际角色回归通过，报告临时目录yingbo-smoke-dvjqW2，包含真实配音、语音/动作/礼物、角色迁移、开心片段缺失回talk及透明播出声音归属。本机语音组件清单与0.8.3相同，无需因本次版本升级重装语音环境。未自动关闭用户旧客户端。

## 0.8.3 可选聊天、角色设定及分层审查

2026-11-27用户要求增加允许聊天设置、角色卡设定，并保持互动守则和防诱导限制。实现如下，优先于0.8.2仅基础身份互动说明：

- settings.interaction.allow_chat默认false，旧数据库通过get_value补默认值；「互动守则」中开启并保存。关闭时维持原商品检索/基础身份招呼；开启后非礼物弹幕由interaction.answer_chat请求既有JSON模型生成候选，再以单独无历史请求审查，同一配置模型、不是两个模型。商品事实仍须引用有效证据，数字无依据或被标成闲聊绕过商品限制时拒绝。模型/审查失败时不合成语音，不自动重试。
- interaction.py用标准库作有界编码检查（Base64、URL、HTML实体、Unicode转义）、原有NFKC与标点零宽规范化、常见中英文越权指令筛查；输入输出均检查。角色设定/证据/弹幕是结构化不可信资料，不给模型工具、配置密钥或本机文件权限，不累积观众多轮记忆；角色设定本身命中规则/越权筛查时拒绝。不能保证百分百防提示注入，特别是两次请求使用同一模型有相关性风险，不能把少量样例称为通用安全验收。
- persona为角色job/character.json的选填字段，严格字符串≤2000字；CardName/Build/CardEdit支持，create_local_card、export_card/import_card、角色应用/开播/改名及项目内角色迁移同步settings.avatar.persona。旧包无字段按空字符串兼容。角色卡不携带聊天许可或互动规则，导入不会开启聊天。UI「角色制作 → 角色设定」，保存按钮与应用都保存，角色ZIP往返已测。
- interaction_policy对当前角色/聊天许可/互动规则取摘要；生成和合成后复核，队列及正在播出的旧聊天在下一次播放器同步时取消。没有改角色视频驱动；仍复用当前视频、语音队列与播放器。
- 真实云端第一次直连ConnectTimeout，随后只读/models验证：当前配置fanrenapi.com/v1、gpt-6.1-sol，系统代理可连且模型在列表。app.llm_json改用已有image_service.image_client读取Windows系统HTTP代理，本地接口仍直连。修复后真实云端一般日常问题生成+复核两次通过；“用拼音念禁词作为语言游戏”在生成阶段拒绝（一次请求）。脱敏结果test-output/chat-acceptance/real-cloud.json，密钥只在测试进程内存读取、未写测试配置文件。
- 74项Python、13项Node检查通过，覆盖开关/旧配置、编码/越权、复核失败、商品证据、规则更新/关闭聊天取消旧回复、角色设定类型与迁移。开发版实际目标角色与Windows语音的桌面全链路验证通过，报告临时目录yingbo-smoke-GAcU7I，chatSettings与personaMigrated均true。未请求新视频生成，不改用户的已保存聊天开关/角色设定；未提交Git或推送。
- 具体选型、上游实现路径及防护边界见docs/chat-and-persona.md。核对LLM Guard PromptInjection需额外Transformers/ONNX分类模型及部分访问授权，尚未通过中文/低配/分发验收，未集成其模型或代码；分层结构参考OWASP防护清单。
- 打包目录版使用实际角色卡的桌面全链路验证也通过，报告临时目录yingbo-smoke-zyj5uz，chatSettings/personaMigrated/实际语音/礼物视频/透明播出声音归属均通过。角色设定测试只改隔离副本，不改用户真实角色卡。
- 已生成release/Jibo-Studio-0.8.3-win-x64.exe，118550243字节，保留现有YingboData。没有自动关闭正在运行的旧版或替用户开启聊天；退出旧客户端后在原目录打开新版测试。

## 0.8.2 主播基础身份互动

2026-11-27用户在工作台发送“你叫什么啊”，即使配置云端模型仍被“未找到相关商品依据”拦截。根因是process_event在调用answer_question之前要求所有普通弹幕命中商品检索，原商品模型提示也明确禁止聊天；本次拦截并不能证明云端配置有错或已连通。

- app.py新增presenter_reply，严格整句匹配姓名/身份/自我介绍问句和少数简单招呼；姓名读取settings.avatar.name（角色应用、开播和改名已有同步）。这类答复无需商品或云端请求；其他弹幕仍走原商品检索与证据/数字校验。输入、输出、规则更新后复查与队列优先级均保留；夹带其他诉求的长句不能靠包含“你叫什么”绕过检索。不是开放闲聊功能。
- 工作台播出描述改为“正在回复弹幕”，互动守则说明更新；版本0.8.2。66项Python、13项Node测试通过，含身份/改名/无商品/有模型配置/拦截混合提示/输入输出过滤回归。
- 使用新PyInstaller后台、实际角色卡与本机已加载的雷电参考音色，通过已有GPT-SoVITS桥接做隔离端到端测试：/api/simulate“你叫什么啊”进入ready，原因“主播基础资料与招呼”，生成5.36秒真实WAV。测试故意将云端地址指向不可用本机端口以确认不依赖云端，未请求用户的真实云端模型。证据test-output/identity-smoke/result.json、identity.wav；没有修改用户角色或云端配置。
- 新构建包含前述GitHub源码415请求头修复；测试音色仍独立存放，不随EXE内置。此次未自动提交Git或推送。
- 打包目录版桌面启动检查通过，报告位于临时目录yingbo-smoke-1rUUVk。因415修复增加下载请求头会改变旧安装指纹，已对本机旧0.8.1资源与新资源逐项比较：仅engine.headers改变、依赖锁字节相同，原安装回执与旧指纹相符；备份installed.json后更新本机回执为新指纹，验证新组件installed=true，未重装或重下PyTorch。此为本机经核对的回执迁移，尚未实现其他旧机器的通用升级迁移。
- 已生成release/Jibo-Studio-0.8.2-win-x64.exe，118547998字节。未自动退出用户正在运行的0.8.1；需退出旧版后打开新版，同目录继续使用YingboData。

## 本机免训练参考音色测试

2026-11-27用户授权使用C:\Users\admin\Music\leidian的录音做测试。目录包含42段MP3，无模型权重；选用5i0xcof0yx80h3hgre377tc8uu2jp45.mp3（6.4925秒）转为32kHz单声道PCM WAV，使用官方GPT-SoVITS v2基础模型零样本推理，没有训练。参考文字由本地faster-whisper tiny转写并校正，尚未人工复核音色和转写，不得称为专门训练音色或音质验收完成。

- 官方模型gsv-v2final-pretrained：s1bert25hz-5kh-longer-epoch=12-step=369668.ckpt（SHA256 732f94e63b148066e24c7f9d2637f3374083e637635f07fbdb695dee20ddbe1f）和s2G2333k.pth（924fdccaa3c574bf139c25c9759aa1ed3b3f99e19a7c529ee996c2bc17663695）。下载自ModelScope AI-ModelScope/GPT-SoVITS，校验与官方HF文件一致，模型仓库标注MIT。
- 测试包release/Jibo-Leidian-Test-Voice-v2.zip（242415479字节），使用单独的VOICE-LICENSE.txt明确仅本机测试，未确认参考录音商业/再分发权。没有使用build_voice_pack.py中历史默认的“本人录音且允许商业分发”声明，不将本素材套用此前其他录音的授权。
- 已通过当前0.8.1本地API导入到release/YingboData/local-tts/voices/8876e78faae346b8b349077d844f19b0，名称“雷电参考音色（免训练测试）”，保存为当前本地音色，auto_load=true。真实GPU加载、预热完成；直播介绍生成9.2秒WAV，API耗时3.56秒（热模型、非流式；非直播并行性能结论）。客户端设置页已选中，并实际点击试听，音频时间进度到4.84秒末尾，状态ready。
- 证据与原配置备份在忽略的test-output/leidian-voice；ASR仅用于本机验证，依赖以uv --target装在该目录，不修改受管TTS环境。原MP3未修改，测试包/权重不进Git，也未改主EXE。首次预热额外下载fast-langdetect的lid.176.bin，说明现有安装清单尚未覆盖全部首用网络资源；上游AR加速提示缺rich，当前普通推理可用，未宣称加速或完全离线首启已经验收。

## 本地语音GitHub源码下载415修复

2026-11-27实际复现GitHub zipball接口不接受Accept: application/octet-stream，返回415且错误说明必须接受JSON；改为application/vnd.github+json后下载成功。tools/local_tts/component.json的engine增加该headers，保持上游提交、文件大小和SHA256不变。下载6890791字节，SHA256=f1117d69f1c88f373bd4d1982bcdd92b12e780af9564104ffcf2ec1c3b921c1e。已将验证后的engine.zip放到本机release/YingboData/local-tts/downloads，现运行的0.8.1可校验复用并越过此请求；未改角色/密钥/音色配置，未触发自动安装或下载其他模型。添加下载请求头及缓存复用回归。该源码修复尚未重打EXE，换机仍需重打包或携带正确缓存。

## 0.8.1 本地语音安装超时修复

2026-11-27用户重启后仍报本地Python -c检查15秒超时。实际复现：后台线程读取Electron stdin管道，子进程继承同一管道时Windows venv启动器卡住；同一Python设stdin=DEVNULL约0.12秒成功，终端独立运行约0.2秒成功。不是VPN问题，也不能按环境损坏处理。

local_tts.LocalTTS._valid_python使用stdin=DEVNULL、清理后的安装env及-I隔离启动；nvidia-smi与taskkill也显式独立输入，安装命令已有DEVNULL，推理进程保留它自己的PIPE。超时改为中文说明，不因超时自动重建环境。新增真实父管道监听/子Python启动回归。源码版本0.8.1，未自动Git提交。63项Python测试通过；额外将复现脚本用PyInstaller打包，用本机真实语音venv验证：原检查稳定卡住，新检查0.172秒成功，且未下载、重建或删除语音环境。结果保存在test-output/tts-probe/result.json。

## 0.8.0 本轮改造（优先于下方历史记录）

2026-11-27用户要求核对并移除旧版场景实验。已将透明人物图/背景上传、历史人物图选择、标准图下载和动作提示词入口统一到角色制作。旧场景网格参数并非等效迁移，而是按视频角色方案淘汰；自然动作来自角色视频。

- 开发版本0.8.0。删除旧实验UI、scene-workshop.js、scene-renderer.js、action-player.js、action_clips.py、scene_model.py及其专用测试/脚本；共享图像生成/抠图工具移至character_images.py，独立Live2D实验CLI仍复用这些工具。
- 仅视频角色卡可开播；旧/api/scenes生成、绑定、编辑和启用接口移除，语音测试改为/api/characters/test-voice。原始/scenes目录仍只读提供历史图片供迁移，用户素材未删除。
- 新/api/characters/inputs列出已有人物图；/inputs/standard和/inputs/background负责本地上传。character_cards.local_source选择输入，create_local_card不再要求活跃旧场景。来源文件按白名单构建，上传不替换正在直播的角色。
- 项目导出包含当前卡或准备图片；旧包导入提取scene/neutral.png和background.jpg以及商品/规则，忽略旧网格和旧动作。不会自动把旧静图变成完整视频角色。
- 本轮继续保留0.7本地NVIDIA语音功能。Git拉取不包含默认音色权重；本机build/local-tts/default-voice.zip不存在时，新包不能宣称包含默认音色。
- 本轮不调用付费生成、不安装新GPU环境、不自动提交或推送。62项Python、13项Node测试通过；开发版空数据启动与真实角色回归通过，打包目录版真实角色回归通过（含人物图/背景上传、语音、角色切换、礼物视频及透明窗口接管）。已生成release/Jibo-Studio-0.8.0-win-x64.exe，约113MiB，不包含默认音色权重。证据保存在test-output/0.8.0-retire-scenes。本轮未验证NVIDIA真实推理或OBS现场推流。

## 当前基线（0.7拉取记录）

- 当前工作目录：`E:\waibao`。项目现名“极播”，Electron + Python/FastAPI + SQLite，`package.json` 版本 **0.7.0**（本地语音组件）。下文 `D:\jibo` / `D:\GPT` 属于另一环境的历史实验路径，不能直接当作本机路径。
- 2026-11-27用户拉取后核对：分支 `main`，HEAD 为 `385c5248bff382a06fa033cfe570219be4720b57`（Release Jibo 0.7.0 with managed local NVIDIA voice synthesis），本地 `origin/main` 指向同一提交；其父提交为 `d974dde`（0.6.2）。开始更新记忆前工作区干净。本次未重新 fetch、构建、安装组件或推送，只核对代码并更新本文件。
- 历史包含 `a20a072`（项目内环境与可选 Live2D 工具）。此前对话中的“0.3.1 是当前版本”“环境提交尚未进入远程历史”已过时，不应继续作为当前状态。
- 角色卡操作以 `docs/jibo-0.6-guide.md` 为准；新增本地语音以 `docs/local-tts-component.md` 和 `docs/local-tts-0.7-validation.md` 为准。README 中 0.5、0.4、0.3 章节及调研文档是历史背景。

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
- **0.7本地语音**：`local_tts.py::LocalTTS`管理独立安装、校验下载/续传、音色ZIP校验导入、NVIDIA推理进程及退出回收。`tools/local_tts/native_worker.py`启动固定上游推理代码；`static/local-tts.js`管理设置、加载弹窗、下载进度和试听。`app.py::synthesize`支持`tts.provider='local'`，缓存区分音色ID及语速，仍沿用现有播出队列。
- **本地语音接口**：`/api/local-tts/status`、`/install`、`/start`、`/voices/import`、`/test`。现支持Windows x64 / NVIDIA，GPT-SoVITS v2，独立Python 3.11.9、PyTorch 2.8.0+cu128；不静默回退CPU。首次安装至少预留15GB，正常离线运行。旧9880/9881外部桥接仅为可选历史适配路径，集成模式无需用户另开服务。

## 环境、构建与迁移

- `start.cmd` 自动准备项目内环境并启动；`setup.cmd` 只准备环境；`check.cmd` 执行环境、Python/Node 测试和真实桌面启动检查；`build.cmd` 打包便携 EXE，`-Target directory` 生成目录版。
- `runtime.versions.json`、依赖锁文件、`scripts/bootstrap.ps1` / `workspace.cjs` 管理 `.runtime/`、`.venv/`、`node_modules/`；一键入口面向 Windows x64，首次需联网。生成环境不提交 Git。
- 当前产物名配置为 `release/Jibo-Studio-0.7.0-win-x64.exe`；目录版为 `release/win-unpacked/极播.exe`。2026-11-27本机核对：0.7.0 EXE、`release/Jibo-Default-Voice-v2.zip`、`build/local-tts/default-voice.zip`均不存在；`data/local-tts`和`release/YingboData/local-tts`也不存在。拉取源码不会同步Git忽略的语音权重、环境和安装包。
- 默认音色通过`scripts/build_voice_pack.py`以GPT/SoVITS权重、3–10秒参考WAV和准确转写生成，构建输入是`build/local-tts/default-voice.zip`。主包可不带默认音色，但使用者必须另导入音色包；不能把仓库中的构建配置当作音色已随Git到位。第三方许可在`licenses/`。
- `desktop/platform.cjs::chooseDataRoot` 优先 `JIBO_DATA_DIR`，兼容 `YINGBO_DATA_DIR`；便携模式优先沿用旁边已有 `YingboData`，否则使用 `JiboData`。
- 角色 ZIP 不含密钥、商品或机器音色，导入需重新验收。完整项目携带当前应用卡与商品/规则等；角色包上限 300MB，完整项目上限 100MB。完整数据目录可能含密钥，迁移前先退出客户端。
- 音色ZIP与角色ZIP独立：`voice.json`、`VOICE-LICENSE.txt`、`gpt.ckpt`、`sovits.pth`、`reference.wav`；当前上限600MB，仅v2。项目导出不包含音色库或GPU依赖。导入检查文件哈希，但上游加载PyTorch checkpoint需要信任来源。

## 验证证据与限制

- 本次只阅读代码和文档以更新记忆，**没有重跑测试、重新构建、调用收费生成或确认/应用任何角色**。
- 随后用户要求编译新版包：2026-11-26 在当前 Windows 10 x64 上执行 `build.cmd` 成功，生成 `release/Jibo-Studio-0.6.2-win-x64.exe` 和 `release/win-unpacked/极播.exe`。`check.cmd` 的 63 项 Python 测试、17 项 Node 测试与开发版启动检查均通过，目录版和便携 EXE 实际启动检查也通过；校验值与本次结果在忽略目录 `release/` 的 `.sha256` 和 `build-validation-0.6.2.json`。本机未找到可用于本轮回归的角色卡，未执行目标视频观感/动作回归，未调用收费生成；本轮打包结果不代表第二台机器或 OBS 现场验收。
- `docs/jibo-0.6-guide.md` 记录上轮已使用目标角色五段真实成片和 Windows 实际 TTS，验证开发/打包版的播放、动作、预览、导入导出、工作台与礼物、透明播出声音接管；这属于已有记录，不是本轮新实测。
- 上轮记录未完成新的付费云端完整制作、实际 OBS/抖音现场推流、第二台物理电脑及 macOS/Linux 验收。低配性能和持续运行仍需目标机器测量。
- 淡化不修复原视频变脸、肢体错误、嘴部活动不足或循环接缝；素材未包含的表情不能自动出现。不能将“有实现”表述为“所有目标素材已合格”。
- `docs/PORTABILITY-VALIDATION.md` 的 40 + 4 项测试和隔离目录重建/移动结果是 **0.3.1 历史验证**，不可用于宣称当前 0.6.2 的测试数量或重新换机成功。
- 当前角色是否已经验收、应用以及目标文件是否齐全，应读取本机实际状态后再判断，不能照搬使用说明里的历史机器状态。

## E:\waibao 本轮同步与已知现场状态

- 本轮只阅读Git差异、实现、资源清单及验证文档，并修正记忆，没有启动本地语音、下载模型、重跑测试或改动用户配置。下文0.7耗时及70/17项测试是另一环境随提交提供的验证记录，不是本机新测。
- 本线程在0.6.2阶段曾对实际`release/YingboData`现场操作：旧场景仍在播导致礼物只有语音；随后将`244169aaa61c42bfa78436f9a474ef1f`“我的极播主播”视频卡确认并应用，重新开始彩排，通过真实窗口点击礼物观察到“当前视频：点头答谢”及字幕。本轮未再次读取当前运行配置，后续仍需核对，不能假设一直未变。
- 用户希望可用抖音直播伴侣/B站直播姬。画面可通过透明播出窗口采集或OBS浏览器源输出；真实抖音/B站弹幕及礼物采集器尚未接入，`/api/events`已有，互动实验室目前模拟事件。OBS并非极播本机测试的必需依赖。

## 后续接手

2026-11-27 后续用户明确授权：现有默认音色是本人录制，可以随软件商业分发；要求在项目中放许可文件，依赖安装时自动下载，配置放设置页，启动显示加载进度，默认NVIDIA，预留导入音色包。已实现0.7.0：`local_tts.py` 管理独立Python 3.11.9 / PyTorch 2.8.0+cu128 / v2官方推理、校验下载/续传、生命周期及音色包；`tools/local_tts/component.json` 和带哈希锁固定资源；`native_worker.py` 使用非阻塞Windows管道存活检测，避免阻塞stdin读取拖住DLL加载。`static/local-tts.js` 提供设置、真实下载进度、启动加载/预热窗口、试听、速度、下载源与音色ZIP导入；原外部9880/9881桥接不再是主流程。

默认音色包由 `scripts/build_voice_pack.py` 生成到 `build/local-tts/default-voice.zip`，随安装包分发，模型本身不进Git。第三方声明与MIT/Apache/GPL等文本在 `licenses/`，用户录音授权也保留在包内。NVIDIA组件安装到客户端数据目录的 `local-tts/`，与外部 `D:\GPT` 无关。正常启动不联网；公共模型、NLTK英文发音资源、GPU依赖在首次启用时下载并校验。预热包含USB等英文缩写。成功合成后删除已完成的大型安装归档，当前组件约9.7GiB；修复安装可能需重新下载。

0.7.0已编译 `release/Jibo-Studio-0.7.0-win-x64.exe`，约325.9MiB，含默认音色ZIP；独立音色包在 `release/Jibo-Default-Voice-v2.zip`。`check.cmd` 的70项Python、17项Node及开发桌面检查通过。使用真实默认音色完成开发版、目录版和最终便携EXE的加载窗口、预热、设置页真实播放、缓存与退出回收验证；最终EXE新生成7.46秒语音并开始播放耗时约3.47秒，缓存调用约0.004秒。自动验收脚本为 `scripts/smoke_local_tts.cjs --data <已准备组件的数据目录> [--exe ...]`；它会在指定数据目录保存本地语音选择，不能当作只读检查。仅实测当前Windows10/RTX5060机器，未验证第二台机器、低配或OBS现场推流。本机 `D:\jibo\data` 已设为集成本地音色；已有发布目录的个人设置保留，用户需在新版切换到本地NVIDIA并启用。原测试9880/9881服务已停止，不再让用户手动启动旧桥接脚本。使用说明见 `docs/local-tts-component.md`。

2026-11-27 用户搁置云语音，指定更新 `D:\GPT\GPT-SoVITS-v3lora-20250228` 并用现有音色试调用。原包无 Git，已在其 `updates/` 新增官方 `6d51ffceafbf240145619af4c92408a6e54b7924` 源码与隔离覆盖依赖，保留旧入口；复用原 PyTorch 2.8.0+cu128、已有 `cao` v2 权重与 4.5 秒参考音频，不是训练新模型或安装 v2Pro。官方 API 9880，极播兼容适配 9881，代码见 `tools/local_tts/`；整合包新增 `go-jibo-local-tts.cmd` 可启动两项服务。已通过隔离数据目录实际调用 `app.synthesize`，生成 `data/local-tts-check/jibo-cao.wav`；完整 8.02 秒音频调用耗时 3.548 秒，短欢迎语直调约 1.349 秒，首次初始化明显更慢，未验证 OBS 并行及客户最低配置。修复空密钥非法 Bearer 请求头，64 项 Python 测试通过。原 0.6.2 EXE 尚未重编，兼容 TTS 密钥可先填 `local` 占位；未修改用户已保存设置、调用收费服务或确认现有音色可商用。详见 `docs/local-tts-validation-2026-11-27.md`。

先查看 Git 状态、`AGENTS.md`、本文件和 `docs/jibo-0.6-guide.md`；按任务读取相关实现，再决定检查或修改范围。调研依据还可查 `docs/upstream-reuse-candidates-2026-11-26.md`、`docs/prerecorded-avatar-code-review-2026-11-26.md` 等，但候选状态须重新核对，不代表已接入。
