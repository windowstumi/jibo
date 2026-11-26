# 预制动画虚拟主播：开源代码实现核对

日期：2026-11-26。任务：核对“待机、通用说话、答谢等均用预生成视频”的实际实现。仅阅读代码与文档，未部署候选项目，未调用付费视频服务，未改动当前播放器。

## 结论

已找到可复用的播放、状态编排与过渡实现；没有在本次核对范围内确认一个可直接交付的“任意图片自动生成全套一致动画＋普通电脑播放＋任意语音准确口型”的完整开源产品。

三种实现应区分：

1. **纯预制素材状态机**：循环待机、有声音时播放通用说话、事件触发一次性动作。最低运行开销，但通用嘴型不对应实际音素。
2. **预制视频身体＋实时口型处理**：LiveTalking、DH_live的相关实现。保留身体视频自然运动，额外按当前音频处理人脸；不是单纯播放说话视频。
3. **预先生成声画配对的整段视频**：固定话术可以准确播放；临时回复需生成新的配对视频。播放便宜，制作仍有等待与成本。

## 1. LiveTalking：最接近“待机＋动作＋语音”的编排

项目：[lipku/LiveTalking](https://github.com/lipku/LiveTalking)，代码头声明Apache-2.0，具体模型和素材另核许可。

直接检查的文件：

- [avatars/base_avatar.py](https://github.com/lipku/LiveTalking/blob/main/avatars/base_avatar.py)
- [avatars/audio_features/base_asr.py](https://github.com/lipku/LiveTalking/blob/main/avatars/audio_features/base_asr.py)
- [avatars/musetalk_avatar.py](https://github.com/lipku/LiveTalking/blob/main/avatars/musetalk_avatar.py)
- [server/webrtc.py](https://github.com/lipku/LiveTalking/blob/main/server/webrtc.py)
- [utils/image.py](https://github.com/lipku/LiveTalking/blob/main/utils/image.py)

实现：

- `AudioFrameData.type`区分正常说话（0）、静音（1）、自定义动作（大于1）。以音频块标签决定状态，不仅依赖是否有可闻声音；普通话语中的停顿不会必然使身体状态反复切换。
- `__loadcustom()`把动作图片序列和可选配套音频读入内存，按动作编号管理。
- `set_custom_state()`设置动作并重置索引；当前版本会检查相应的音频索引是否存在，因此不能直接假设所有无声视频都能不加处理地通过该接口触发。
- `BaseASR.get_audio_frame()`优先输出自定义动作的音频块，动作完成后回到静音状态。
- 静音分支直接输出已有帧，正常说话分支调用`inference_batch()`；MuseTalk子类根据音频特征推理脸部图像，经`paste_back_frame()`按坐标和遮罩融回原始帧。
- `mirror_index()`正向、反向交替取帧，减少循环尾部直接跳回首帧。适合轻微呼吸，不宜直接用于完整挥手/鞠躬：倒放不等于自然回位。
- `process_frames()`中存在约100ms的`cv2.addWeighted()`交叉混合，但本次版本明确为`enable_transition = False`，不能称为默认已经保证无缝。
- 在默认25FPS设置下，视频帧40ms、音频块20ms，同一视频输出周期配两个音频块；WebRTC输出使用PTS控制节奏，设有限队列，避免音画各自随意推进。

对当前项目的价值：采用明确的状态与音频边界、单次动作播放到结束、统一时间轴及可取消队列。不要照搬其GPU推理依赖和所有帧常驻内存方式。

## 2. DH_live mini：原视频循环＋逐帧对齐的人脸处理

项目：[kleinlee/DH_live](https://github.com/kleinlee/DH_live)。主仓库README声明MIT；人物素材、网页角色授权和打包二进制依赖仍需分别核对。

直接检查：

- [web_demo/static/js/MiniLive2.js](https://github.com/kleinlee/DH_live/blob/main/web_demo/static/js/MiniLive2.js)
- [web_demo/static/js/dialog.js](https://github.com/kleinlee/DH_live/blob/main/web_demo/static/js/dialog.js)

实现：

- 创建静音循环`video`，并读取`combined_data.json.gz`里的逐帧人脸数据。
- `processVideoFrames()`先把视频当前帧画到离屏Canvas，锁定同一帧，避免后续处理中视频前进导致脸部坐标错配。
- 从视频角落编码的像素读取帧序号，再取对应的矩阵、点位和脸部区域。
- `dialog.js`把音频数据送给WASM的`_setAudioBuffer()`并用Web Audio播放。
- `processDataSet()`取得`_updateBlendShape()`结果，渲染并通过`_processImage()`处理局部区域，最后把结果放回当前视频的人脸位置。

重要边界：这不是独立嘴PNG，但也不是“全部视频原样播放”。它对脸部仍执行处理；JavaScript调用的是WASM，不能仅凭调用层代码就认定整个底层算法都已验证、可修改或能适配任意二次元图片。

对当前项目的价值：若将来要保留身体视频且改进口型，可以研究逐帧人脸对齐。若用户选择纯预制说话动画，应先不加入这条推理链。

## 3. OBS Studio＋Advanced Scene Switcher：纯视频状态切换的成熟参照

- [OBS媒体源实现](https://github.com/obsproject/obs-studio/blob/master/plugins/obs-ffmpeg/obs-ffmpeg-source.c)
- [Advanced Scene Switcher](https://github.com/WarmUpTill/SceneSwitcher)
- [媒体播放控制](https://github.com/WarmUpTill/SceneSwitcher/blob/master/plugins/base/macro-action-media.cpp)
- [场景切换与过渡等待](https://github.com/WarmUpTill/SceneSwitcher/blob/master/plugins/base/macro-action-scene-switch.cpp)

已核对的实现：

- OBS媒体源提供循环、激活时重新播放、不活动时关闭文件、媒体结束事件等控制。
- 插件提供播放/暂停/停止/重播/定位和等待播放停止，使用媒体状态处理动作结束。
- 场景切换可以指定过渡和时长，并等待过渡结束；动作播完后回到指定场景可通过宏组合完成。

可以搭成“待机视频循环→外部事件切到答谢→媒体结束返回待机”；音频播报期间切到说话场景也可以由外部控制编排。它们不负责图片生成视频、商品知识库、礼物采集或准确口型。

授权边界：这些是独立开源程序/插件；当前查看的Switcher LICENSE为GPLv2正文。可借鉴设计或通过独立程序接口连接，不应默认复制到闭源客户端没有分发义务。

## 4. LiveStream：业务编排参考

[lipku/LiveStream](https://github.com/lipku/LiveStream)的README明确提供循环话术、中间插入弹幕回复、知识库问答和OBS输出，运行时依赖LiveTalking服务。它不是独立的无模型动画播放器，也不负责把任意图片自动制成整套动画。没有因README相似就确认其动画和商业分发条件全部满足本项目。

## 建议采用的实现结构

如果接受通用说话口型，当前项目应采用轻量视频状态机：

- 素材：`idle`循环、`talk`循环、`thanks/wave/present`单次；固定讲稿可另用声画匹配的完整视频。
- 主时钟：以实际音频开始/结束控制说话状态，不只用音量阈值在每次停顿时跳变。
- 切换：当前与候选两个视频槽预加载解码首帧；在已标记的安全姿态附近短时混合，完成后释放旧槽。不同时解码整个素材库。
- 动作：排队、一次播放、自然回位，完成或失败均明确返回；保留停止和声音归属接管的取消机制。
- 循环：素材优先制作成自然首尾闭环，必要时有专门衔接段；不把倒放作为全身动作的默认修复。
- 资源：不必照搬LiveTalking的全帧缓存。以1280×720、25FPS、5秒RGB序列计，未压缩数据约346MB（约330MiB），多段常驻对低配设备不划算。使用压缩视频和有限的解码缓冲更合适。
- 检查：所有视频的身份、相机、角色位置、背景及可切换姿态一致；背景随整帧视频生成时，要检查背景变化会不会暴露切场。

这一结构能实现低成本的完整动画状态切换，但通用说话素材仍无法自动获得任意新语音的音素级同步。该选择需要用户确认，不能借用开源项目名称来掩盖这一限制。

本次阅读的分支为LiveTalking main、DH_live main、OBS master、Switcher master；分支内容会变化。API仓库树与所读源码快照保存在本机忽略目录`test-output/video-player-research/`，不随产品发布。
