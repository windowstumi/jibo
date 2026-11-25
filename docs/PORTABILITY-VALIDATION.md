# Windows 换机与打包验证记录

验证日期：2026-11-26。系统：Windows 10 x64（19045）。版本：0.3.1。

## 已完成

- Node.js 22.16.0、uv 0.13.10、CPython 3.12.9、Python 虚拟环境、npm 依赖及下载缓存均放在项目目录内。
- 从受 Git 管理的源码和未忽略的新文件创建独立副本，目录名包含空格及中文；没有复制已安装的 Python、`.venv` 或 `node_modules`。
- 测试进程的 PATH 排除全局 Python/Node，并清除可能干扰运行的 Python、Node 和 PowerShell 环境变量。
- 在源码副本重新安装依赖：40 项 Python 测试、4 项 Node 测试、真实 Electron 启动及后台健康检查全部通过。
- 在源码副本完成 PyInstaller 后台和 Electron 便携 EXE 构建。把目录版移动到另一处含空格、中文的目录后，再次启动检查通过。
- 将便携 EXE 复制到当前项目的 `release/` 后，实际启动检查通过；程序界面、桥接、后台健康、无模型时的开播拦截均正常。
- 当前项目最终执行 `check.cmd` 再次通过以上 40 + 4 项测试及真实桌面检查。
- 可选环境 `live2d.cmd -Mode doctor` 通过。复用已保存的六张图片，使用项目内 Java/PSD2Live CLI 重新编译，并经本机运行中的 PSD2Live MCP 完成六个肩/肘/腕关节及招手、介绍、答谢动作。导出 MOC3、CMO3、可编辑工程；模型引用的 19 个文件全部存在。招手、介绍 GIF 均为 67 帧。

## 验证边界

这是同一台机器上的隔离源码、重新安装和移动目录验证，尚未在第二台物理电脑或全新 Windows 用户上执行。隔离安装复用了下载归档及包缓存，未复用已安装环境；不是全程冷缓存网络测试。原始机器报告保存在 `.runtime/verification/latest.json`，不随源码提交。

可选 Live2D 的 MCP 步骤复用了本机已启用的编辑器服务；新电脑可能需要先在 PSD2Live 设置中启用 MCP。本次没有重新付费生成图片，也未验证任意新图片的自动绑定质量。配置文件仍需按角色校准，正式客户端仍使用原有 2.5D 渲染器。

自动环境脚本支持 Windows 10/11 x64，本次实测 Windows 10。macOS、Linux、ARM64 没有实测。Windows 系统语音取决于目标机器已安装的音色；图片和云语音服务需要目标机器自行配置。

## 复验命令

在源码根目录：

```powershell
.\start.cmd                    # 自动安装缺失环境并启动
.\check.cmd                    # 检查环境、测试、真实桌面启动
.\build.cmd                    # 编译便携 EXE
.\build.cmd -Target directory  # 编译可复制目录版
.\setup.cmd -WithLive2D        # 安装可选 Live2D 工具环境
.\.venv\Scripts\python.exe scripts/verify_portable.py --build
```

最后一条命令创建独立源码副本并执行换路径验证；添加 `--cold-cache` 可不复制已有下载缓存。源码压缩包不包含运行环境、个人数据、图片或密钥，首次安装需要联网。便携 EXE 已包含正式客户端所需运行时，不包含可选 Live2D 编辑工具。
