# 项目内环境与打包

## 支持范围

一键下载、启动和构建入口面向 Windows 10/11 x64，使用系统自带 Windows PowerShell；有 curl.exe 时优先使用它，否则回退到 PowerShell 下载。首次需要联网，访问 Node.js 官方站点、GitHub 官方发布、Python 包仓库和 npm 锁文件里的包地址。无需管理员权限，也不修改系统 PATH、执行策略或系统 Python。`.cmd` 的执行策略参数仅作用于其子进程。

`runtime.versions.json` 固定 Node.js 22.16.0、uv 0.13.10、CPython 3.12.9、可选 PSD2Live 3.8.4。Node/uv/PSD2Live 压缩包校验固定 SHA256；Python 由固定版本 uv 下载管理；Python 构建与可选依赖使用带哈希锁文件，npm 使用 package-lock.json。

## 命令

| 入口 | 作用 |
| --- | --- |
| `start.cmd` | 自动安装缺少的依赖并启动桌面客户端 |
| `setup.cmd` | 只创建或同步本项目的环境 |
| `setup.cmd -Force` | 强制按当前锁文件同步依赖 |
| `check.cmd` | 环境检查、Python/Node 测试、真实桌面启动检查 |
| `build.cmd` | 后台 PyInstaller + Windows 便携 EXE |
| `build.cmd -Target directory` | 生成完整可复制目录版 |
| `setup.cmd -WithLive2D` | 额外安装拆层依赖与项目内 PSD2Live/Java |
| `live2d.cmd -Mode doctor` | 检查可选 Live2D 环境 |

环境目录：

```
.runtime/
  node-v22.16.0-win-x64/       Node 与 npm
  uv-0.13.10/                 Python 环境管理器
  python/                    CPython 3.12.9
  psd2live-3.8.4/             可选，含 Java
  downloads/                 经校验的运行时压缩包
  cache/                     包缓存
.venv/                       本项目 Python 依赖
node_modules/                本项目 Electron 与构建依赖
build/                       打包中间结果
release/                     EXE 或目录版
data/                        本机数据，不提交
```

以上生成目录均不提交到 Git。提交的是版本清单、锁文件和安装脚本。若移动项目路径，入口会检测失效或来自其他路径的虚拟环境，将其移到 `.runtime/old-venv-*` 后重建；不会静默使用系统 Python。安装完成且锁文件未变化时，正常启动不重新联网安装。

## 网络与离线边界

首次安装需要互联网。下载失败会保留已成功安装的部分，再次运行可继续；只有完整且哈希正确的压缩包才会解压。GitHub 下载提供官方网站和官方 API 两个入口；UV 和 PSD2Live 大文件支持分段读取，防止中间代理截断文件。Python 默认使用清华 PyPI 镜像，下载仍须符合锁文件中的官方发行包哈希，可用 `UV_DEFAULT_INDEX=https://pypi.org/simple` 覆盖。Electron 默认沿用 npm 锁文件使用的 npmmirror 镜像，校验值由锁定的 Electron 包提供；构建辅助程序也使用该镜像。可通过 `ELECTRON_MIRROR` / `ELECTRON_BUILDER_BINARIES_MIRROR` 覆盖下载地址。预先下载的 wheel 可放到 `.runtime/downloads/wheels/`，安装时同样校验哈希。

若网络要求 npm/Electron 镜像，可在当前终端设置 npm 配置或 `ELECTRON_MIRROR` 后重跑 `setup.cmd -Force`。不要关闭 TLS 校验。API 密钥在界面输入，Live2D CLI 通过隐藏输入或 `IMAGE_API_KEY` 读取，不写入源码。

安装包无需运行时下载 Python/Node；但图片生成和云端语音仍依赖你配置的 API。未包含模型权重、第三方平台账号、GPU/CUDA、参考图片或个人生成数据。客户端本身不要求 NVIDIA GPU；独立重型 AI 服务不在此打包范围。

## 换机验证

应在未包含 `.runtime/.venv/node_modules/build/release/data` 的新目录运行一键脚本，验证单元测试、Electron 实际启动，再构建并启动 `release/win-unpacked/Yingbo Studio.exe`。打包冒烟测试使用临时数据目录，不读取个人 API 密钥，不付费生图。

macOS/Linux 不是 Windows EXE 的运行目标，须在对应系统用 README 的手工流程编译。当前一键环境和可选 Live2D 编译入口仅承诺 Windows x64；其他架构需另行提供匹配的运行时与原生依赖。

本次实际执行结果与测试边界见 [换机验证记录](PORTABILITY-VALIDATION.md)。

## Live2D 实验

代码已迁入 `tools/avatar_pipeline/`，通过参数传入输入图片、输出目录和校准配置，不再引用开发者机器上的安装目录。保留了调用结果不明时禁止自动重试的保护。输出可重新编辑和分发；环境可重建不等于绑定质量全自动，详见该目录 README。
