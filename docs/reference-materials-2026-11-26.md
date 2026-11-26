# 极播参考表演素材核查

核查日期：2026-11-26。仅查找来源、读取许可与检查一个官方输入视频；没有调用收费生成，没有替换默认参考库，没有改动播放器。当前尚未找到七类动作齐全、构图统一、可商用再分发且经过目标角色验证的成品包。

## 找到的具体素材

| 来源与文件 | 适用方向 | 检查结果与状态 |
| --- | --- | --- |
| [Wan2.2官方animation输入](https://github.com/Wan-Video/Wan2.2/blob/main/examples/wan_animate/animate/video.mp4) | 说话与手势的接口测试 | 已下载检查：1920×1080、30fps、3.536729秒，含音轨；抽帧看到真人电视主持人坐姿半身、桌面与字幕图案，不是干净的全身七状态模板。仓库Apache-2.0不能自动证明其中第三方节目、肖像等权利已清理；不内置为商用素材 |
| [Mixkit 28287：Man talking head-on on a chroma background](https://mixkit.co/free-stock-video/man-talking-head-on-on-a-chroma-background-28287/) | 通用说话、介绍手势候选 | 实际详情页标16秒、60fps、4.67MB，绿幕、正面说话和手势，标Stock Video Free License；尚未下载或逐帧检查。需裁剪到当前接口允许的2–8秒；半身/全身覆盖、首尾姿态仍待确认 |
| [Mixkit 39798：Young woman waving at her cell phone on a video call](https://mixkit.co/free-stock-video/young-woman-waving-at-her-cell-phone-on-a-video-39798/) | 微笑招手候选 | 实际详情页标11秒、24fps、3.6MB；厨房场景、对手机招手、Medium Shot，标Stock Video Free License。手机可能遮挡、视线和全身构图不适合，需先筛选，不能直接作为标准全身模板 |
| [Blender Studio Rain v2](https://studio.blender.org/characters/rain/v2/) | 有明确授权的参考表演制作底座 | 页面明确免费、CC-BY、提供下载与署名要求，含人物骨骼和面部控制；这是角色rig而非现成七段视频，需离线制作/渲染，不能列为已经可直接导入的MP4 |

Mixkit详情页的“允许商用视频作品”不等于允许把原始片段当作软件素材库再分发。已读取[Mixkit Terms](https://mixkit.co/terms/)：对向第三方提供素材、stock/inventory形式整理分发有约束。AI动作迁移处理和随EXE/素材包分发的许可需分别确认；当前不把这些候选自动下载、上传云端或随极播打包。以上是具体筛选候选，不是已完成授权的推荐包。

Rain页面要求署名：`Rain Rig © Blender Foundation | cloud.blender.org`。若以后用它制作参考，需同时检查采用的动画、声音等素材各自许可。离线3D参考模板不意味着最终角色变成3D，也不要求直播客户运行Blender；这条路线本轮未实施。

## 排除和待确认的来源

- [Trinity Speech-Gesture](https://trinityspeechgesture.scss.tcd.ie/)：当前页面明确仅非商业科研，禁止未授权第三方分发和商业用途，不适合作为极播商用素材库。
- [CMU Motion Capture](http://mocap.cs.cmu.edu/)：首页允许包含在商业产品中、禁止直接转售数据（包括转换形式）。数据是骨骼运动，不能直接提交给万相video_url，也不能补齐自然说话和表情，故只属需适配候选。
- Pexels、Pixabay页面在本次网络返回403，未把其素材或许可当作本轮已核实结果。

## 为什么素材仍需筛选

官方[预处理指南](https://github.com/Wan-Video/Wan2.2/blob/main/wan/modules/animate/preprocess/UserGuider.md)说明：参考人与目标角色比例差异会引起形变；需要检查姿态重定向，不能假定任意真人视频对任意动漫角色都有效。开源预处理参数也不等于当前托管API开放相同控制。

极播需要：单人、固定镜头、脸和手清楚、匹配半身或全身构图，动作前后回到统一姿态。待机与说话需自然循环；开心/思考需可见表情；答谢/招手/介绍需自然回位。参考只提供表演驱动，衣服的合成仍取决于生成模型，不等于有真实衣物物理或衣料分割。

正式内置应选同一来源、同一机位、获得云端处理和软件分发授权的一套表演。应先验证待机、说话、答谢这三种，再扩充情绪和其他动作；七类全配齐是当前产品实现的限制，不是万相单次调用的要求。万相单次只需要该次使用的一条参考视频。

本机检查文件保存在忽略目录`test-output/reference-research/`。官方样例SHA256：`80f3cfe3786a7f8a94844476448fb45e7e115216ddcdaad14b0b88223be597e7`。这些检查只证明源文件属性，不是目标角色生成效果验收。
