# 映播 · 虚拟人直播客户端

使用 Electron + Python/FastAPI + SQLite 的本地桌面客户端。当前版本 **0.3.1**。

## 快速开始：全新克隆

**Windows 10/11 x64：首次联网后运行一条命令即可。无需预装 Python、Node.js、npm 或 Java。** 脚本将固定版本的 Node.js、uv、Python 下载到项目的 `.runtime/`，在项目内创建 `.venv/` 和 `node_modules/`。不修改系统 PATH，不依赖开发者电脑上的其他目录。

Windows PowerShell：

```powershell
git clone https://github.com/windowstumi/jibo.git
cd jibo
.\start.cmd
```

也可以在资源管理器双击 `start.cmd`。单独安装环境或检查：

```powershell
.\setup.cmd          # 仅准备项目内环境
.\check.cmd          # 环境、Python/Node 测试、桌面启动检查
```

Windows 打包：

```powershell
.\build.cmd
.\build.cmd -Target directory
```

输出为 `release/Yingbo-Studio-0.3.1-win-x64.exe`。目录版位于 `release/win-unpacked/`，复制时必须保留整个目录。安装包内包含 Python 后台和 Electron，使用者不需安装开发环境。

**Live2D 实验工具另行启用：** `setup.cmd -WithLive2D` 或 `live2d.cmd -Mode doctor`。它会把 PSD2Live 的便携版（含 Java）和拆层依赖放进本项目。用法见 [Live2D 工具说明](tools/avatar_pipeline/README.md)。生成图片仍需自己的图片 API 密钥；绑定需校准图层/关节配置，不能把实验脚本当作任意图片自动绑定服务。正式客户端目前仍使用原有 2.5D 渲染器。

固定版本、校验下载、换路径重建、离线范围、支持平台和验证方式见 [环境与打包说明](docs/PORTABLE.md)。macOS/Linux 仍采用后文的手动安装方式，并须在目标系统构建；本次一键环境入口仅支持 Windows x64。

**Git 仓库不包含本机生成的角色、安装包或已配置密钥。** 全新克隆后需要自行配置图片服务、生成场景，或导入已有项目包。请勿直接照搬本文提到的本机验收路径。

## 0.3.1 衣料隔离与直播模型统一

- 删除旧版独立嘴部元素、绘制、设置及校准接口。直播只使用场景模型的表情贴图。
- 直播工作台可选择已生成场景，开始彩排会将所选场景用于预览和播出。没有模型时明确提示，不能用静态图片替代开播。
- 上传参考图片不再覆盖正在使用的直播场景。
- 裙摆不再对整行网格顶点施加位移。衣料遮罩内使用纹理流动，范围外的腿和手不受影响；保持原有轮廓以避免露出缺失图像。
- 可在形象工坊拖动衣料边界点、保存范围。已有场景自动本地补齐遮罩，不调用生成服务。
- 对输入素材中与衣料交叠的裸露肢体，需要在范围编辑器中将它们排除；此版不承诺任意图片的自动服装语义分割。

## 0.3.0 动态场景模型

已新增从原图到正面角色、说话/闭眼表情、独立背景、网格绑定及场景预览的完整流程。生成4张图片后，本地运行裙摆风动、头部/身体变形、表情纹理和背景变化，支持导入导出。详细设计、实际调用记录、限制和验收步骤见 [ACCEPTANCE.md](ACCEPTANCE.md)。

本机生成的验收样例位于 `release/YingboData/scenes/`，只存在于开发机器，未提交到 Git。角色是可驱动2.5D网格模型，不是Live2D moc3或3D骨骼模型。

## 0.2.1 图片连接修复

图片重绘服务增加“跟随系统代理 / 直连 / 手动代理”。Windows 默认读取系统代理；macOS/Linux 使用代理环境变量。手动模式可填写 `http://127.0.0.1:7890` 等 HTTP 代理地址。这是请求代理配置，不会启动、关闭或修改 VPN。全局 VPN 隧道由操作系统路由控制，软件只能确认是否使用显式代理。

在“接入设置 → 图片重绘服务”点击“保存并测试图片连接”，会读取模型列表并显示请求是否经过代理，不生成图片。通过后再在形象工坊重绘。若切换了系统代理，下一次请求会读取新配置。

已区分连接超时、代理不可达、生成响应超时、鉴权、额度、非 JSON 和不兼容返回等错误。支持 `data[0].b64_json` 与 `data[0].url` 两种结果。生成响应超时不会自动重试，先查服务后台是否已完成，避免重复扣费。

独立桌面客户端：Electron 窗口 + 内置 Chromium 画面/音频 + Python/FastAPI 后台 + SQLite。发布包包含 Python 运行时和依赖，目标电脑无需安装 Python、Node 或另开浏览器。HTML/CSS/JavaScript 仅作为客户端内部渲染技术。

## Windows 便携版

程序：`release/Yingbo-Studio-0.3.1-win-x64.exe`。

- 将 EXE 放到可写文件夹，双击运行。同目录创建 `YingboData` 保存项目和配置。
- 关闭程序后，将 **EXE 与整个 YingboData 文件夹**复制到另一台 Windows 电脑即可迁移。
- 不要从只读盘或不可写的系统目录运行。退出主窗口会停止播出并结束后台。
- `release/win-unpacked/` 是目录版，必须整目录复制，不能只复制其中的 EXE。
- 当前是未签名开发构建；正式分发需要 Windows 代码签名、macOS 签名及公证。

## 开发启动与构建

执行 `start.cmd` 或 `start.ps1` 启动客户端；它会自动准备环境并复用项目的 `data/`。

Windows 一键环境：

```powershell
.\setup.cmd
.\start.cmd
```

Windows 打包：

```powershell
.\build.cmd
# 或分步执行
.\.venv\Scripts\python.exe scripts/build_backend.py
npm run dist:win
```

macOS / Linux：

```sh
python3.12 -m venv .venv
.venv/bin/python -m pip install -r requirements-build.txt
npm ci
npm start
# 在目标系统和CPU架构上构建后台，再打包
.venv/bin/python scripts/build_backend.py
npm run dist:mac    # macOS ZIP / .app
# 或 npm run dist:linux  # Linux AppImage
```

不要把 Windows 的 `build/backend/` 拿到 macOS/Linux 打包。Python、Pillow 等包含平台相关二进制，必须在对应 OS/CPU 上重建。`requirements-build.lock.txt` 是 Windows x64 的带哈希构建锁；macOS/Linux 使用 `requirements-build.txt` 在目标平台解析构建工具。`.github/workflows/desktop.yml` 提供可手动触发的三个系统构建流程，Windows 走同一套一键脚本。macOS Intel/Apple Silicon 需分别构建，其他平台结果不等于本机实测。

如果宿主设置了 `ELECTRON_RUN_AS_NODE`，启动 Electron 前需清除；`start.ps1` 已处理。可通过 `YINGBO_PYTHON` 指定开发时的 Python，通过 `YINGBO_DATA_DIR` 指定数据目录，通过 `YINGBO_PORT` 指定首选端口。

## 跨平台设计

| 项目 | 处理方式 |
|---|---|
| 界面、音频、字幕和嘴型 | 内置 Chromium，同一音频驱动嘴部 |
| Python 后台 | PyInstaller 按目标平台打包，用户不用配置环境 |
| 数据 | 与程序资源分离；普通安装用用户目录，便携版用 EXE 旁的 YingboData |
| 启动和关闭 | 自动启动后台、健康检查；关闭客户端结束后台；端口冲突时自动分配 |
| Windows 语音 | 使用目标机器已安装的中文 SAPI 音色，缺少时明确报错 |
| macOS/Linux 语音 | 默认使用兼容 `/audio/speech` 的本地或云端服务 |
| 迁移 | 项目包带走形象、参考图、商品、规则和答谢模板；服务密钥需重新填写 |

没有把 Windows 系统音色当作跨平台能力。CosyVoice 等模型可以通过兼容服务接入，当前没有内置大型模型和 PyTorch。直接复制数据目录到其他系统会保留旧音色配置，建议用项目导入导出并重新设置 TTS。

## 第一次使用

1. 接入设置填写图片服务的基础地址、模型、密钥和代理，先测试连接。Windows 默认可使用已安装的中文系统音色，其他系统需配置兼容 TTS。
2. 形象工坊上传参考图，点击生成完整场景；会产生4次图片服务调用费用，不自动重试。也可导入已有项目包。
3. 载入场景预览，检查表情、绑定和衣料范围，确认后用于直播。生成模型前不能开始彩排，不再使用独立嘴部替代。
4. 商品知识库填写真实参数、价格、FAQ 和分段讲解稿；示例商品仅供验证。修改稿件或音色后重新开始彩排。
5. 直播工作台选择角色场景和商品，开始彩排，模拟商品提问、屏蔽语句和礼物，观察处理记录和语音。

场景生成会标准化角色、生成表情及独立背景，再去绿幕并绑定。它不是自动拆层绑定的 Live2D；衣料使用遮罩内纹理流动，外轮廓固定。单纯上传图片不会自动变成模型。

## 项目迁移

点击“导出迁移项目”，通过原生保存对话框导出 ZIP。在另一客户端点击“导入项目”。导入会替换形象、商品和规则，并在当前数据目录的 `backups/` 中先保存旧项目。

项目包不含 API 密钥、音色配置或缓存；当前机器的服务密钥不会被导入覆盖。数据目录中的 SQLite 含本机密钥，当前未使用系统密钥链加密。复制完整目录前先退出客户端，不要只复制正在写入的 SQLite 主文件。

## 透明播出窗口与 OBS

“打开播出窗口”打开独立透明桌面窗口，顶部悬停条可拖动，右上角关闭，也可通过“播出”菜单关闭。

OBS 推荐使用客户端“复制地址”的浏览器源，宽1080、高1920。这样不依赖各操作系统的透明窗口捕获。地址含本机访问凭据，请勿公开分享。客户端内置服务只监听本机，不对局域网开放。

OBS 启用“通过 OBS 控制音频”。播出窗口和 OBS 比工作台预览优先；不要同时启用多个播出画面。关闭后预览约8秒恢复接管；切换时当前片段从头播放。

默认首选8765端口，冲突时选择空闲端口。重启后以客户端复制的新地址为准。程序只控制本地节目，不会自行启动抖音直播。

## 事件接入

接入设置显示实际地址。`POST /api/events`，请求头为 `Authorization: Bearer <事件接入密钥>`。

```json
{"event_id":"comment-001","kind":"comment","username":"小林","text":"多久发货？"}
```

```json
{"event_id":"gift-001","kind":"gift","username":"小林","gift":"鲜花","count":3}
```

重复编号不会再次处理；礼物连击应由采集端合并。抖音采集器暂未包含。事件密钥与桌面内部访问凭据不同。

## 验证

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm run test:desktop
npm run smoke:desktop
node scripts/smoke_desktop.cjs "release/win-unpacked/Yingbo Studio.exe"
```

Python 检查覆盖过滤、知识库、迁移、鉴权、真实 Windows 配音和队列。Node 检查覆盖平台路径和数据目录。无场景的桌面检查验证启动和禁止静态图开播；已有场景时，用以下命令进一步测试实际配音、播出、迁移和衣料像素隔离（替换最后一个路径）：

```powershell
node scripts/smoke_desktop.cjs --dev "D:\YourData\scenes\<scene-id>"
node scripts/smoke_desktop.cjs "release\Yingbo-Studio-0.3.1-win-x64.exe" "D:\YourData\scenes\<scene-id>"
```

测试结束自动退出，数据保存在临时目录，不修改正式项目，也不发起付费图片生成。

## Git 提交范围

保留源码、测试、内置示例资源、npm锁文件、Python依赖、版本清单、构建脚本和说明。`.gitignore` 排除 `.runtime/`、`.venv/`、`node_modules/`、`build/`、`release/`、`data/`、`YingboData/`、测试输出、SQLite、日志、环境密钥文件、证书以及 `.vs/` 等 IDE 缓存。不要把 `.venv` 提交到 Git：虚拟环境带有绝对路径且不能跨平台搬运，另一台机器应由脚本按锁文件重建。

服务密钥保存在用户数据目录的 SQLite 中；当前未使用系统密钥链加密，请勿上传数据库或整份用户数据。安装包应单独通过发行渠道提供，不加入源代码提交。

默认规则与证据检查不能保证识别全部不适宜内容或模型错误。正式播出前需用真实商品、实际服务商和真实平台接口做验收。目前尚不包含完整 Live2D 绑定、账号体系、自动更新或长期无人值守保障。

## 文件

- `desktop/main.cjs`：窗口、菜单、原生文件对话框、后台生命周期。
- `desktop/preload.cjs`：受限的桌面功能桥接。
- `desktop/platform.cjs`：跨平台路径与数据目录。
- `backend_entry.py`：内置后台入口、端口选择、父进程关闭处理。
- `app.py`：商品、规则、语音、事件、迁移与本地鉴权。
- `static/`：客户端内置界面和播出渲染。
- `scripts/build_backend.py`：后台打包。
- `scripts/smoke_desktop.cjs`：桌面集成检查。
- `build.ps1`、`start.ps1`：Windows 构建和开发启动。
