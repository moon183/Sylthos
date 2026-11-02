# 历史交接全文存档（只读参考）

这是2026-10-23文档整理前的HANDOVER全文，保留最初需求、历次建议、技术细节和当时验收记录。原文字句未修订，因此其中“当前”“待验收”“未同步”仅指相应历史时期，旧操作与默认值不能直接使用。

当前状态、接口和用户最终决定见[现行交接手册](../../HANDOVER.md)与[状态速查](../../CURRENT_STATE.md)。历史相对路径原本基于项目根目录；引用历史资料时请回到根目录查找。不得按存档中的reset --hard示例直接回退用户工作。

---

# 项目交接文档（HANDOVER v2.1）—— 手势识别 PPT 演讲优化系统（Sylthos）

## 接手入口：2026-10-23 F阶段原项目同步

**请先读 [CURRENT_STATE.md](CURRENT_STATE.md)**，再读本文历史记录和 [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md)。当前用户已认可现状，已同步到 `D:\Kimicode\Gesturerecognition`，D盘601项测试与九页原生启动检查通过；详情见 [SYNC_RECORD.md](SYNC_RECORD.md)。下一步才更新DEMO等材料。

下文按时间记录的“未同步原项目”“待验收”“验证弹窗”等描述属于当时状态，不作为当前实现或最新任务。最新验证模块是页内四列表格、自适应高度；E只修收笔同帧冲突。C4与E第1/3项暂缓。



## 最新交接补充：2026-10-23

- D首批：按用户要求在原三个模块和“已录制的手势”之间加入④验证手势，保留训练集准确率。入口打开独立验证窗口，选目标、测试者代号和次数；准备1.5秒、识别3秒、收手1.5秒。准备与收手不进入自定义识别器，每轮以首次接受结果计分；整轮无手标为无效。支持已知动作正确/认错/未识别，以及无关动作误接收计数。
- 验证自动开启监控；若由验证开启，关闭验证窗口时停止监控。手势验证期间（含查看本次结果）绕过PPT手势控制管线，不写训练样本；报告单独保存于evaluations/，页面可查看最近报告，各次JSON均保留。测试者仅记录代号，不宣称已核实为陌生人；跨人汇总、训练参与身份核验和历史报告选择尚未实现，D不能标记全部完成。回退点`backup/d-validation-20261023`，等待用户实机验收。
- C3已完成真实设备复测：59.35秒内三次后台清理分别1320.227/1340.611/372.694ms，GUI最大采样间隔39.724ms，无超过50ms间隔。识别FPS中位29.72，不等同屏幕帧率。C4检查发现的小窗口、高DPI适配问题由用户明确暂缓，本批不处理。

- C3：真实测量定位停止监控1349.42ms同步等待导致界面停顿；已改为request_stop + finished，清理期间按钮“正在停止…”且禁止重启，关闭窗口等线程结束再销毁，防止旧状态回流。回退点`backup/c3-monitor-stop-20261023`；具体数据与测试见IMPLEMENTATION_PLAN.md。未改摄像头后端、驱动、采集参数及语音停止逻辑，待真实设备验收。用户config.json未提交，项目外已有备份。

- 当前在独立副本工作，未同步原项目。C2仅按用户要求修复校准向导收起途中重新展开时高度归零：从面板当前高度接续，完全隐藏后仍从零展开，保留展开后文字浮现。
- 用户明确接受现有导航动画期间忽略收起、导航同步向导高度的行为，本轮不修改；动画对象清理和停止线程等待亦不在本轮范围内。
- 修改前存档：`backup/c2-wizard-reopen-20261023`。新增三个不同收起进度的回归用例，修复前均失败，修复后Windows原生Qt校准/预览专项26项通过。完整结果见IMPLEMENTATION_PLAN.md本轮记录；等待用户实机验收。

> 本文档写给后续接手优化本项目的 AI 工具（Kimi Code / ChatGPT Codex 等）与开发者。
> v1.0 版交接文档由 Kimi Code 写于 2026-09-11（见 git 历史）；v2.0 由 Kimi Work
> 在第二轮深度优化（2026-09-12 ~ 09-13）后重写；**本 v2.1 由 Kimi Code 在第三~五轮
> （2026-09-14 ~ 09-19：验收修复 + 三大新功能 + 1165×720 布局改版 + 主题页）后
> 全面修订续写**，新增/修订内容集中在**第七部分（近期改动全录 + GUI 美化详细计划 +
> 已知问题清单——接手者最优先读）**。
>
> **给接手 AI 的首要规则**：本仓库的一切行为准则以 `AGENTS.md` 为准（每次改动必须
> commit、必须写/更新测试、交付前测试全过、实测反馈驱动的改动必须附带回归测试）；
> 技术边界以 `SPEC.md` 为准（依赖白名单制，新增依赖或网络功能必须经所有者批准并修订 SPEC）。
> 本文档只做"理解项目"的导读，不替代上述两份硬规范。

---

## 第一部分：项目的诞生与演进

### 1.1 用户的原始构想（2026-09 项目立项时的原意）

用户是一名大学生，这是他的**大学生创新创业项目（大创）**。原始想法：

> 经常看发布会或讲课时，演讲人站在屏幕前会随情绪自然做出各种手部动作，而现在控制
> PPT 大多靠翻页笔——按键动作会打断思绪。能不能用摄像头识别演讲中的自然手势来
> 控制 PPT，让演讲更流畅？

他一开始列出的设想（右手为例）：从右向左挥=下一页、从左向右挥=上一页、握拳张开=
放大、张开握拳=恢复、五指张开滑动=移动放大位置、食指点击=播放视频。随后越构想越大：
打响指唤激光笔、隔空圈画重点、实时字幕、AI 实时翻译、整页翻译成英文、最终封装成
一个"有使用场景、有深度、又简洁灵动的 PPT 控制软件"。

**关键理解**：用户要的不是"手势翻页器"，而是**对演讲 PPT 环节的整体体验优化**。
他的产品直觉是"灵动、丝滑、无打扰"——后续所有 UI 动画、防误触、配额制设计都源于此。

### 1.2 开发史（五轮）

**第一轮（2026-09-05 ~ 09-11，Kimi Code 结对完成）**：MVP → 手势体系 v2 多轮打磨 →
Fluent UI 美化 → 智能化（自定义手势、工具箱、实时字幕）。产出：全部规划功能落地、
276 个测试全绿、exe 打包、v1.0 交接文档。**详细历史见 git log（108+ commits）与 v1.0
HANDOVER（git 历史可查）。**

**第二轮（2026-09-12 ~ 09-13，Kimi Work 深度优化）**：用户实测发现自定义手势"根本无法
识别"，并委托对整个项目做"成熟、实用、优美"的深度优化。本轮按"先调研再动手"的原则：
- **三轮调研**（见 `RESEARCH_ROUND3.md`）：Google Soli / 华为隔空手势 / visionOS /
  Midas Touch 学术解法 / $1 模板匹配识别器 / gesture spotting / OctoPocus 反馈可视化；
- **P0 自定义手势根治**（详见 4.2）：三个根因定位并修复 + $1 模板引擎双引擎仲裁；
- **P1 基础手势隐患修复 ×5**（详见 4.1 附注）；
- **丝滑专项 S1-S11**（详见 3.5/4.3）：书写过渡冻结、光标 120Hz 插值、COM 阻塞根治、
  计时粒度、浮层插值等；
- **Phase A 新功能 A1-A7**（详见 4.4-4.8）：噪音自适应 VAD、置信度可视化、备注提词、
  字幕翻译+字幕条重做、站位引导、彩排统计页、人脸门控。

**第三轮（2026-09-14，Kimi Code，验收修复 + 三个暂缓功能落地）**：A1-A7 逐项实机验收
修复（输入电平表、字幕条可拖动、彩排清除按钮等）；三个"暂缓功能"全部落地——
**流式字幕第三模式**（sherpa-onnx Zipformer CTC 21MB，边说边出字）、**手势灵敏度
标定向导**（测量手长/挥手/保持，只放宽不收紧地写个性化阈值）、**一键演示**（开监控+
打开 PPT+开始放映）；手势说明从弹窗搬为独立导航页。详见 7.1。

**第四轮（2026-09-15 ~ 09-17，Kimi Code，GUI 布局改版 + 细节打磨）**：窗口
1280×720 → **1165×720 黄金比例**（用户亲定，逐像素规格化双态布局）；校准向导从
对话框改为**预览页内嵌模块**（自动开监控、三段式子卡、内容淡入淡出）；悬浮窗手位
小点与状态圆点删除；标题栏定制（**Sylthos 花体** + 按钮满高）；各页注释灰字统一、
页面标题与导航统一；自定义页黄金比例重排（录制+训练左列）；语音页 2+1+1 排版；
设置页禁滚轮误触 + 8 个新可调项；日志页滚动回弹修复。详见 7.2。

**第五轮（2026-09-19，Kimi Code，主题页）**：新增第九页「**主题**」（仿 GitHub
FLClash 项目主题页）：主题模式三选 / 主题色网格（三阶预览色块 + 自绘 HSV 取色
对话框）/ 纯黑模式；全 app 自绘元素主色跟随 `themeColor()`。过程中挖出并修复三个
存量/库级问题（ScrollArea 深色蒙亮纱、setThemeColor 信号时序、暗主题主色提亮）。
详见 7.3。

### 1.3 用户的产品偏好（接手者必须内化，每轮都被反复强调）

- **界面美观是硬需求**：等间距栅格、黄金比例、圆角一致、动画丝滑、**窗口尺寸绝不被
  子页面撑大**（1165×720 是信仰级约束，2026-09-15 用户亲定，见 4.8 适配铁律）；
  用户对像素级对齐极度认真——会给具体像素规格，接手者要代入真实布局公式**核算闭合**
  （历史上用户三次算错都被核对纠正并接受）；用户说"边距一致"时意思是"由居中自然产生，
  不写死"；
- **逻辑一致性**：同类功能行为必须一致（如各页面"未开监控"提示要一样）；
- **零打扰**：未激活时手随便动都不能误触；放映前比划不能翻页；Toast 不能乱弹；
- **丝滑是信仰**：用户对"卡顿/抖动/不跟手/画直线"极度敏感，为此项目做了 S1-S11 专项
  （光标链路、书写状态机、COM 阻塞、浮层插值），任何会引入顿挫的改动都会被退回；
- **自主可控**：手势能自定义、指令能自定义绑定、路径能自选、功能有总开关、阈值全可配、
  **主题色/主题模式可自选（第五轮主题页）**；
- **可回退**：用户明确要求每个改动可快速回退——因此每个修复独立 commit、关键版本打
  Git tag（`v1.0-baseline` 最初完好基线、`v1.1-dual-engine` 自定义手势修复版、
  `v1.2-feature-complete` 功能齐备布局改版前、`v1.4-pre-theme` 主题页前），
  单个改动用 `git revert <commit>` 撤销；
- **答辩导向**：所有功能最终服务于"大创答辩现场演示稳定、有亮点"。

---

## 第二部分：当前成果全景（2026-09-19，v2.1 修订）

### 2.1 能力清单（当前版本）

**手势控制（规则 + 时序状态机）**：激活开关（五指张开保持 0.7s）、挥手翻页（手势单元
状态机 + 方向锁 + 收势屏蔽 + **收势中立区相对化**）、缩放模式（档式缩放/✌️切方向/
食指平移/中心锚定/**pan_speed 速率可配**）、激光笔模式（光点跟随/工具循环/握拳书写/
捏合点击）、八字黑屏、G 键原生导航（指向选择+捏合跳页+**COM 安全关网格**）、
三指聚光灯（自绘浮层+**QRegion 无缝绘制**）、OK 统一退出、双手缩放（默认关）。

**自定义手势（轨迹识别 v2，本轮根治）**：食指或握拳作画 → **四路收笔**（换掌型/减速/
静止超时/丢失超时）→ **双引擎仲裁**（纯 numpy MLP + $1 模板匹配，结论必须一致 +
距离比拒绝门）→ 热重载即时生效 → 绑定 16 种指令；**免训练也能识别**（$1 模板即样本）；
**置信度可视化**（Toast 带数值 + 悬浮窗小胶囊 + 练习页行内显示 + 拒绝双引擎明细反馈）。

**演讲工具箱**（全部可由自定义手势触发）：开始放映、回到第一页、跳到最后一页、
白屏、黑屏、擦除墨迹、视频播放/暂停、静音、倒计时浮层、指针聚光环、截图存档、
字幕开关、**备注提词（A3 新增）**。

**实时字幕（语音识别）**：能量 VAD 分段（150ms 预缓冲 + **噪音自适应底噪**）→
三种模式：离线 SenseVoice（零网络整句出字）/ **离线流式 Zipformer CTC（第三轮新增，
21MB，边说边出字 + 句尾停顿自动定稿）** / 在线百炼（可"转写+翻译"双行字幕）→
底部字幕条（A4 重做 + **第三轮可鼠标拖动换位**）；
热词矫正（只作用于中文行）；**输入电平表**（快攻慢放动画 + 峰值驻留 + 琥珀阈值标线，
识别"没反应"时一眼区分麦克风/阈值/模型问题）。

**GUI**：qfluentwidgets FluentWindow **九页**（预览/手势练习/自定义手势/语音识别/
彩排统计/设置/**主题（第五轮新增）**/手势说明/日志），悬浮状态窗（缩略图+
**站位引导虚线框**+**识别小胶囊**+**备注预览区**+模式+手型+页码+FPS，可拖拽），
Toast 反馈。（~~状态圆点/手位小点~~ 第四轮按用户要求删除——悬浮窗指示已足够。）

**标定向导（第三轮）**：预览页内嵌模块（第四轮由对话框改为内嵌，自动开监控，
**校准期间屏蔽一切手势识别**）——引导做手长测量（2s）→ 挥手×3 → 保持×2，
实测数据 → `compute_suggestions` **只放宽不收紧**地生成阈值建议 → 应用（写 config+
热更新）/恢复默认；悬浮窗活动行同步显示"校准中"。依据：Chalmers 实验个人微调
83.7%→97.5%，换场地/换光线/紧张手抖时识别更稳。

**一键演示（第三轮）**：预览页「一键演示」= 开监控 + 打开 `demo.ppt_path`（设置页
可换文件）+ 开始放映（COM 直达，文件不在则复用 PowerPoint 当前文稿）。

**彩排统计（A6）**：彩排控制（开始/结束+实时计时）、彩排报告（总时长/各指令次数/
每页停留/被拒次数+导出 Markdown+**清除按钮**）、累计统计面板（**清除按钮**）。

**人脸在场门控（A7，SPEC 3.5）**：mediapipe 内置 face_detection，无人在场忽略激活、
离场超 `face_gate.absent_disarm_s`（当前 9s）自动退激活。

### 2.2 量化指标与工程状态

- **测试：419 个 pytest 全绿**（单元 + 离线回放 + GUI offscreen + 集成）；
- 挥手识别实测 20/20（第一轮验收数据）；管线 ≥25 FPS（720p，检测输入已降采样 960×540）；
- **卡顿系列已根治**（第二轮实测确认）：书写/平移/指向全部丝滑（详见 3.5）；
- 校准向导实测全流程走通（第三轮）；主题页机制有严格一致性测试（第五轮）；
- `cli accept` 量化验收（全手势矩阵 `--full` **尚未跑**，用户暂缓）。

### 2.3 交付物与回退点

- 源码（本仓库，Git 管理）；
- 打包 exe：`dist/GesturePPT/GesturePPT.exe`（**注意：exe 是第一轮旧版，第二~五轮
  改动后均未重打包，收尾时须重新执行 `python tools/build_exe.py`；主题页/深色模式
  在 frozen 环境从未验证**）；
- 文档体系：AGENTS/PRD/PROJECT/RESEARCH/RESEARCH_ROUND3/SPEC/PLAN/ROADMAP/README/DEMO
  /**GUI_BEAUTY_PLAN（美化调研与候选清单）** + 本文档；
- **回退点**：`git tag v1.0-baseline`（第一轮完好基线）、`v1.1-dual-engine`（自定义手势
  修复版）、`v1.2-feature-complete`（功能齐备、布局改版前）、`v1.4-pre-theme`
  （主题页前）；单点撤销用 `git revert <commit>`；全部回到基线用
  `git reset --hard v1.0-baseline`（会丢弃之后全部改动，慎用）。

---

## 第三部分：技术架构（当前实际）

### 3.1 分层与数据流

```
摄像头(cv2, MSMF+MJPG, 720p)
   │  CameraCapture（独立线程，始终取最新帧，黑帧自愈）
   ▼
HandTracker（tracking.py，MediaPipe 封装）
   ├─ 整帧直检（960×540 降采样提速 44%）/ BPF 三态机（DIRECT/ACQUIRE/TRACK，
   │  长时间无手自适应退避降频）
   └─ 人脸检测（每 6 帧 320px 小图，face_gate 门控输入）
   ▼ HandFrame(handedness, landmarks[21], hand_scale, ts)
Pipeline（pipeline.py，每帧唯一入口 process(hf, controls, face_present=None)）
   ├─ PoseClassifier（单帧几何分类 + N 帧确认消抖）
   ├─ 各检测器（gestures/*.py）→ GestureEvent
   ├─ DecisionEngine（模式状态机 + 功能开关 + 配额制 + 指令注册表）
   ├─ 书写状态机（pointing/writing/lifting，过渡冻结，见 4.3）
   └─ 连续控制（激光点/书写/平移/光圈，目标点输出）
   ▼
controls 字典：{"ppt": PptComController（COM 指令 + 250ms 后台轮询缓存）,
                "keyboard": KeyboardController（按键 + CursorStreamer 光标插值）,
                "spotlight_ui"/"ring_ui"/"notes_ui"/"countdown_ui"/"subtitle_ui"（浮层桥接）,
                "feedback_fn"（Toast）, "screenshot_fn"}
   ▼
GUI（PySide6 + qfluentwidgets）：GestureWorker(QThread) 跑上述管线，
     一切跨线程通信走 Signal；ASRManager 独立线程（离线 SenseVoice / 流式
     Zipformer `asr/streaming.py`（accept_waveform + endpoint 检测 + reset）
     / 在线百炼三引擎插拔）；RehearsalRecorder 统计；校准向导经 worker
     `wizard_sample` 信号逐帧采样（无需第二路摄像头）
```

**关键架构约定（勿破坏）**：
- 新增功能 = 新增检测器 + 注册指令处理器，**只注册不改动核心链路**；
- 手势事件统一 `GestureEvent(type, confidence, timestamp, data)`；
- 模式枚举：`DISARMED / ARMED / LASER / ZOOM / NAV / SPOTLIGHT`，互斥规则在
  `DecisionEngine._ALLOWED` 表；
- 所有阈值集中在 `config.json`（见 4.9 全键表），调参不改代码；**设置页改动经
  `worker.request_config_reload()` → `pipeline.reload_config()` 热更新，不重启监控**。

### 3.2 目录结构（实际现状，第五轮后）

```
Gesturerecognition/
├── src/
│   ├── main.py / cli.py / config.py
│   ├── capture.py            # 摄像头线程采集（MSMF+MJPG，黑帧自愈）
│   ├── tracking.py           # MediaPipe 封装 + BPF + 降采样 + 人脸检测
│   ├── pipeline.py           # 管线 + 指令注册 + 书写状态机 + 连续控制 + 门控
│   ├── decision.py           # GestureType/GestureEvent/Mode/DecisionEngine
│   ├── rehearsal.py          # A6 RehearsalRecorder 彩排统计 + 报告格式化
│   ├── calibration.py        # 校准测量器×3 + compute_suggestions（只放宽不收紧）
│   ├── recorder.py / accept.py / overlay.py / plugins.py
│   ├── gestures/
│   │   ├── static_pose.py / swipe.py / activation.py / hold.py / filters.py
│   │   ├── laser.py          # ✌️唤起/捏合/LaserPointer（自校准+reset）
│   │   ├── tap.py            # 食指点击（提前冻结 in_progress）
│   │   ├── nav.py / ok_exit.py / spotlight.py / eight_hold.py / zoom.py / twohand.py
│   │   ├── trajectory.py     # 轨迹：分段器(四路收笔)/录制器/运行时识别器(双引擎仲裁)
│   │   ├── dollar.py         # $1 Unistroke 模板匹配引擎（纯 numpy，免训练可用）
│   │   └── mlp.py            # 纯 numpy 单隐层 MLP（含拒绝类 OTHER）
│   ├── control/
│   │   ├── ppt_com.py        # COM 指令 + 250ms 后台轮询线程（页码/放映/备注缓存）
│   │   └── keyboard.py       # 键鼠模拟 + CursorStreamer（120Hz 插值 + ink 通道）
│   ├── asr/
│   │   ├── capture.py        # 麦克风采集 + 能量 VAD + 噪音自适应底噪
│   │   ├── offline.py / online.py（translate 双行提示词）/ hotwords.py
│   │   ├── streaming.py      # 流式 Zipformer CTC 引擎（第三轮，边说边出字）
│   │   ├── base.py / manager.py（_correct_zh_line 只矫正中文行；partial_ready 信号）
│   └── gui/
│       ├── fluent_window.py  # 主窗口：九页 + 布局双模式逐帧插值（apply_blend）+ 浮层调度
│       ├── theme_page.py     # 主题页（第五轮：模式/主题色网格/自绘取色对话框/纯黑）
│       ├── title_bar.py      # 标题栏定制（Sylthos 花体 + 三按钮满高）
│       ├── wizard_inline.py  # 校准向导内嵌模块（预览页画面下方展开，内容淡入淡出）
│       ├── rehearsal_page.py # A6 彩排统计页
│       ├── asr_page.py / custom_gesture_page.py / help_page.py / selftest_page.py
│       ├── overlays_mixin.py # 浮层与 Toast 接线（含 A2/A3/A5 新增接线）
│       ├── status_overlay.py # 悬浮窗（ThumbLabel 站位引导/识别胶囊/备注区）
│       ├── toast.py / worker.py / main_window.py（旧版保留，仅测试用）
│       # 已删除：status_dot.py（状态圆点，第四轮用户要求删）、
│       # calibration_wizard.py（旧对话框版向导，第四轮被内嵌版取代）
├── config.json               # 全部阈值 + theme 节（见 4.9）
├── tests/                    # 419 个 pytest
├── custom_gestures/          # 轨迹样本 CSV + model.json（gitignore）
├── models/                   # ASR 模型（sensevoice/paraformer/zipformer_ctc，gitignore）
├── recordings/ logs/ screenshots/  # 运行产物（gitignore）
├── hooks/                    # PyInstaller hooks
└── tools/                    # build_exe / diagnose_custom_gesture / profile_pipeline 等
```

### 3.3 线程模型（当前）

- **主线程**：Qt UI。所有控件操作只能在这里；
- **GestureWorker（QThread）**：采集+MediaPipe+管线+控制执行；启动时
  `set_win_timer_resolution(True)`（timeBeginPeriod(1)，见 3.5）；
- **cursor-stream 线程**（CursorStreamer）：以 ~120Hz 指数趋近插值移动系统光标，
  ink 通道（mouse_event 笔级事件）单独限流 60Hz；
- **ppt-com-poll 线程**（PptComController 内）：独立 COM 连接，250ms 轮询
  （页码/总页数/放映状态/当前页备注）写缓存——**管线线程只读缓存，永不直接调 COM**；
- **ASR 识别线程**：音频段解码；结果经 Signal 回 GUI；
- **浮层**：全屏透明置顶 Tool 窗口，由主窗口/mixin 持有；聚光灯/指针环内部用
  FollowSmoother（Qt 主线程 ~125Hz 插值）。

### 3.4 防误触体系（这个项目的灵魂，勿轻易改）

1. 总开关激活制（张开手掌保持 0.7s + 漂移阈值带像素下限）；
2. 配额制（command_quota=1 一次性激活）；
3. 模式互斥 + 挂起（`_ALLOWED` 表），OK 统一退出；
4. 放映前门控（show_gate）：未放映只有激活和"开始放映"类自定义手势放行；
5. **人脸在场门控（A7）**：无人在场忽略激活，离场 9s 自动退激活；
6. 挥手后 600ms 宽限期：保持/沿检测器重置；
7. 录制屏蔽：录制自定义手势期间一切识别关闭；
8. **作画优先权**：有效作画期间挥手/缩放沿/导航保持全部挂起；
9. 轨迹拒绝：双引擎仲裁（MLP + $1 必须一致）+ 距离比拒绝门 + 合成负样本；
10. 末页/首页边界保护（COM 层拦截 + 末页点击拦截，缓存读页码）；
11. 书写停笔迟滞 + 过渡冻结（明确非书写手型持续 ~230ms 才抬笔，期间笔尖冻结）；
12. 挥手收势屏蔽（RETRACTING，**中立区相对本次挥手起点**，站偏不死锁）；
13. **校准屏蔽（第三轮）**：`pipeline.calibration_active` 期间一切手势识别关闭
    （与录制屏蔽同分支旁路；悬浮窗活动行显示"校准中"）；
14. **练习态豁免放映前门控**（`pipeline.practice_active`，练习时通常不在放映——
    第三轮实测反馈）。

### 3.5 光标与浮层运动链路（丝滑专项的最终形态，重点理解）

**问题史**：用户实测"指向/书写/平移全都卡顿，画线会突然变直线，预览也卡"。
逐层定位后的完整结论（每一层都是真实修过的坑）：

1. **管线本身健康**（探针实测：快速书写运动下检测 avg 8.5ms、零停顿）；
2. **真凶①：COM 轮询阻塞**——PPT 渲染墨迹时主线程繁忙，管线上的 COM 页码轮询/
   门控查询被同步阻塞 300-690ms（帧耗时看门狗实锤）。**修复：COM 全部状态读取挪到
   独立 250ms 轮询线程，管线只读缓存**；
3. **真凶②：光标输出=摄像头帧率**——30Hz 阶梯跳点。**修复：CursorStreamer 独立线程
   120Hz 指数趋近插值**；ink（笔级 mouse_event）限流 60Hz + 最小步长 1px +
   ink_tau 30ms（更跟手）；
4. **真凶③：Windows 计时粒度 15.6ms**——插值线程实际只能跑 ~64Hz 且步进变粗。
   **修复：timeBeginPeriod(1)；插值器每 tick 按真实 dt 计算趋近系数**；
5. **真凶④：指尖/掌根共用 One Euro 滤波器**——食指↔握拳切换时滤波器在两种定位
   之间滑翔（竖直拖线的元凶）。**修复：书写状态机 + 掌根独立滤波器 + 锚点 offset**；
6. **真凶⑤：自绘浮层不走光标通道**——聚光灯/指针环只有 30Hz 直给。
   **修复：FollowSmoother（Qt 主线程 ~125Hz 插值）；聚光灯绘制改 QRegion 整数像素
   裁剪（此前矩形+路径方案在小数像素接缝处产生亮线）**；
7. **平移手感**：`zoom.pan_speed=0.5`（半速插值被误删后补回的可配速率）+
   `pan_deadzone_px=1.5`（3px 死区临界启停造成抖动）。

**数据流（指向类）**：管线 30Hz 目标点 → One Euro（`laser.one_euro_*`，knuckle 用
`laser.knuckle_*` 更跟手）→ CursorStreamer（120Hz，真实 dt 趋近，tau=`cursor.tau_ms`）
→ OS 光标。**数据流（书写/平移）**：同上但走 ink 通道（`cursor.ink_hz=60`、
`cursor.ink_min_step_px=1.0`、`cursor.ink_tau_ms=30`、mouse_event 笔级事件）。
**数据流（浮层）**：管线目标点 → Signal → FollowSmoother（125Hz）→ 浮层重绘。

---

## 第四部分：各子系统详解（最终版）

### 4.1 手势判定细则（当前阈值以 config.json 为准）

| 手势 | 判定逻辑要点 | 配置键 |
|------|------------|--------|
| 激活 | OPEN_PALM 保持 hold_ms + 漂移 < max(0.08×handScale, min_drift_norm) | activation.* |
| 挥手翻页 | 手势单元状态机（详见 4.1 注）；direction_invert=true（向右挥=下一页）；**收势中立区=本次挥手起点**（home_relative） | swipe.* |
| 缩放 | 沿检测（握拳→张开=一档；✌️切方向后张开→握拳=缩小档）；中心锚定（move_to_immediate）；**平移=食指，速率 pan_speed=0.5，死区 pan_deadzone_px=1.5，增益随放大倍率** | zoom.* |
| 激光笔 | ✌️ 保持唤起；模式内 ✌️ 循环工具；指尖子区域映射（**进入指向模式时以手位自校准，偏移有界**）+ One Euro→屏幕坐标；书写走状态机（见 4.3）；捏合=单击（捏合中冻结光标） | laser.* / pinch.* |
| 黑屏 | EIGHT 手型（拇食中指约 90°，角度窗经真实手部照片标定 cos 0.25~0.70）保持 | blackout.* |
| 导航 | 食指保持 1.5s → kb "g"（原生网格，**G 键成功回执才标记网格已打开**）；食指移动系统鼠标；捏合/点击跳页（**下压/捏合进行中光标冻结**）；退出优先 COM「跳转当前页」安全关网格（Esc 兜底） | nav.* / tap.* |
| 聚光灯 | 三指保持唤起；光圈跟随指尖（FollowSmoother 插值 + QRegion 无缝绘制） | spotlight.* |
| OK 退出 | OK 手型保持 400ms；统一退回 ARMED 并复位对应效果 | ok_exit.hold_ms |
| 双手缩放 | 默认关闭 | twohand.* |

**P1 修复附注（第二轮对基础手势做的 5 个隐患修复，每个独立 commit）**：
①收势中立区相对化（站偏不再卡死 RETRACTING）；②检测器阈值热更新（设置页改即生效）；
③激活漂移容差加像素下限（3 米远处激活不再过难）；④跨模式滤波器状态重置（光圈/
指针环不再从旧位置飘）；⑤指向映射站姿自校准（站偏用户的舒适手位=屏幕中心）。

### 4.2 自定义手势 v2（本轮根治，用户曾实测"根本无法识别"）

**三个根因（离线诊断工具 `tools/diagnose_custom_gesture.py` 定位，可复跑）**：
1. **收笔只有一条路**（换明确手型×5 帧）——画完垂手/保持不动 = 笔画永不结束 =
   识别从未发生。**修复：四路收笔**——换掌型 + 笔尖减速（<0.5 手长/s 持续
   `end_still_ms=400`）+ 静止超时 + 手丢失超时（`lost_end_ms=450`，短丢帧仍桥接）；
2. **导航手势抢占**：食指慢画 >1.5s 被"食指保持唤导航"抢占切走模式。**修复：有效作画
   期间挂起导航保持计时**（静止食指保持无移动量，真导航不受影响，有回归测试）；
3. **全链路零反馈**。**修复：拒绝时 Toast 给双引擎明细**（"MLP「画圈」0.42 /
   模板「打勾」0.61"），识别成功未绑定指令也有提示。

**识别引擎（`gestures/dollar.py` + `gestures/mlp.py`）**：
- $1 Unistroke Recognizer（Wobbrock et al., UIST 2007）：重采样 32 点→旋转归零→
  正方形缩放→质心归一→±45°黄金分割搜索匹配；**模板即样本，免训练可识别**；
- 仲裁规则：双引擎都在场时**必须结论一致且各过阈值**（`prob_threshold=0.55`、
  `dollar_threshold=0.75`、`dollar_margin=0.03` 距离比拒绝门）；单一引擎在场按其规则；
- 置信度可视化（A2）：成功 Toast 带数值、悬浮窗小胶囊、练习页行内"最近置信度"。

### 4.3 书写与平移（丝滑专项核心，用户"改了很久没成功"的顽疾）

**书写状态机**（`Pipeline._pen_control`）：
- `pointing`：仅食指（或明确非握拳）时定位；**握拳首帧立即冻结光标，并在「冻结点」
  落笔**（冻结点=最后发出的指尖目标，不再跟踪下落中的指尖）；
- `writing`：掌根经**独立 One Euro 滤波器**（`laser.knuckle_min_cutoff/beta`）+
  **落笔时刻锚点 offset** 增量跟随（笔尖位置与握拳前严格连续，无跳变无滑翔）；
- `lifting`：出现明确非握拳手型 → **笔尖冻结计数**，持续 ≥7 帧（约 230ms）才在
  原地抬笔；UNKNOWN/握拳回退不断笔（运动模糊桥接）。

**平移**（缩放模式）：食指竖起 = 按住左键拖动；起步重置滤波器锚定当前手位；
`pan_speed=0.5` 速率、增益随放大倍率、1.5px 死区；目标点直给（插值由输出层承担）。

### 4.4 演讲工具箱（16 个指令）

`_CUSTOM_COMMANDS` 表（pipeline.py）：翻页×2、黑屏/白屏、激光笔开关、开始放映、
回到第一页、跳到最后一页、擦除墨迹、视频播放/暂停、静音、倒计时浮层、指针聚光环、
截图存档、字幕开关、**备注提词（notes_toggle，A3）**。无浮层环境（CLI）返回
False = 未执行（不耗配额不弹 Toast）。GUI 下拉选项 `COMMAND_CHOICES` 与标签表三处
同步（有测试防漏加）。

### 4.5 语音识别（实时字幕 + 翻译）

- **采集分段**：sounddevice 16kHz 单声道 30ms 帧 → 能量 VAD（150ms 预缓冲、
  静默 500ms 切段、离线 12s/在线 25s 段长上限）；
- **噪音自适应（A1）**：底噪低方差判别（环境噪音能量近似恒定、语音起伏大）——
  最近 1 秒能量呈低方差时底噪地板快速贴近其 20 分位，阈值 =
  `max(energy_threshold, noise_margin × 底噪)`；安静环境行为与原实现一致；
- **离线**：SenseVoice Small int8（约 234MB，GUI 一键下载）；
- **离线流式（第三轮新增）**：Zipformer CTC 中文 int8（约 21MB，`asr/streaming.py`
  StreamingEngine：accept_waveform 喂帧 + endpoint 检测 + reset）——边说边出字
  （`manager.partial_ready` → 字幕条 `set_partial` 占"当前句"位实时刷新，带尾随光标），
  句尾停顿 `asr.stream.endpoint_silence_s=1.2` 自动定稿转正式行；模型 GUI 一键下载
  （ghproxy 镜像，GitHub 直连超时教训）；
  - 注意：**SenseVoice 对纯噪音会幻觉短文本**（"그."/"Yeah."）——已知正常现象；
  - 麦克风底噪 RMS≈0.01 的设备上 `energy_threshold=0.01` 会压在底噪上导致"完全没反应"
    ——第三轮加**输入电平表**（语音页+阈值标线）解决可诊断性（A1 验收发现）；
- **在线**：百炼 qwen-audio-turbo；**翻译模式（A4，`asr.translate`）**：提示词改
  "转写并翻译成英文，严格两行输出"，字幕条显示中文+英文小字；**热词矫正只作用于
  中文行**（`_correct_zh_line`）；
- **字幕条 UI（A4 重做 + 第三轮可拖动）**：更小巧——无翻译 64px 高/有英文 100px，
  宽 1040，默认字号 24，当前句亮白加粗 + 英文小字（**第五轮起跟随主题色**）、
  上一句暗色，占位提示"正在聆听…"；**鼠标可拖动换位（用户位置记忆）**；
  ⚠️ `SubtitleOverlay._partial` 必须在 `__init__` 初始化（paintEvent 异常 PySide6
  会吞噬并刷一堆 QPainter 报错——第三轮实测踩过，有测试守护）。

### 4.6 备注提词器（A3）

COM 轮询线程顺带读当前页备注（`NotesPage.Placeholders(2).TextFrame.TextRange.Text`，
缓存读取零阻塞）→ worker `notes_changed` 信号 → 悬浮窗备注区（前 2 行/60 字省略，
有备注才显示、悬浮窗局部加高，不影响主窗口）；点击备注区或自定义手势「备注提词」
唤起/关闭 `NotesOverlay`（底部 900px 大字卡，翻页自动刷新，无备注显示占位）。

### 4.7 彩排统计（A6）

`src/rehearsal.py` 的 `RehearsalRecorder`（worker 持有）：彩排控制（start/stop）、
指令计数（dispatched 事件）、页码停留（COM 缓存变化）、自定义手势被拒计数
（feedback 含"未识别"）。GUI 页「彩排统计」（套滚动区，已纳入窗口尺寸回归测试）：
彩排控制卡（按钮+实时计时）、报告卡（Markdown 报告 + 导出 logs/ + **清除按钮**）、
累计统计卡（**清除按钮**，清零 `reset_totals`；第三轮起两卡均有清除）。

### 4.8 GUI 体系与适配规则（血泪清单，接手者必读，**美化前必须逐条遵守**）

**窗口**：FluentWindow，**固定 1165×720**（信仰级约束，2026-09-15 用户亲定
黄金比例，原 1280×720）。导航栏收起 48px / 展开 165px，动画 300ms。
标题栏定制（2026-09-16）：左上 Sylthos 花体（数学粗斜体字形）+ 右上三按钮
满高（46×48，hover 盖满整条，事件过滤器接管绘制、图标垂直居中）。

**适配铁律（全部是实测 bug 换来的，新增页面/美化时逐条对照）**：
1. 其它页面适配预览页，**不得反向撑大窗口**：卡片多的页一律套 `ScrollArea`；
2. `stackedWidget.setMinimumSize(1, 1)`（设 0 会被 Qt 忽略）；
3. 布局动画要"边缩放边移动"：逐帧插值 setFixedSize，时长与导航动画一致；
4. 提示文字类内容放独立子控件，动画时只平移不重排版（否则字体抖动）；
5. 复选框对齐：左对齐放进居中容器，保证所有 √ 同一竖线；
6. CardWidget 内置 `clicked` 信号，**不要覆盖成普通函数**（会 AttributeError），
   **也不要重定义成带参信号**（基类 mouseReleaseEvent 的无参 `clicked.emit()`
   会 TypeError——主题页 _ModeCard 实测踩过；要参数就在 connect 处 bind）；
7. 重建控件列表时只继承数据、不带旧控件引用（deleteLater 后访问 = C++ object deleted）；
8. 文字全部 setWordWrap，防窄卡溢出；
9. 浮层 show 后加 `raise_()`（Windows 全屏 PPT 前台时兜底置顶）；
10. 工作线程更新 UI 一律走 Signal；
11. **新增**：新页面必须加入 `tests/test_fluent_window.py` 的
    `test_nav_toggle_never_resizes_window_on_any_page` 页面清单（A6 已示范）；
12. **新增**：悬浮窗/浮层是独立 Tool 窗口，它们的局部加高/显隐不影响主窗口
    （A3 备注区已示范）；
13. **新增（2026-09-19）**：`ScrollArea` 必须 `enableTransparentBackground()`
    ——默认视口用系统调色板恒亮白，深色主题下内容区会蒙亮纱；
14. **新增（2026-09-19）**：自绘元素的主色一律读 `themeColor()` /
    `accent_color(dark_canvas=True)`（恒深底浮层用暗色提亮变体）；换色重刷要
    **双挂** `qconfig.themeChangedFinished` 与 `qconfig.themeColorChanged`
    （后者由 setThemeColor 发射且在 updateStyleSheet 之前——要打掉被重刷覆盖的
    自定义样式需再推迟一轮事件循环，title_bar 已示范）。

**主题页（2026-09-19 新增，仿 FLClash 主题页）**：导航页「主题」（在设置之后，
`src/gui/theme_page.py`）。主题模式三选卡（自动/浅色/深色）；主题色网格
（默认蓝 #009faa + 7 预设 + 自定义色右键删除 +「+」自绘 HSV 取色对话框：
色相/彩度渐变滑条 + 11 档明度网格 + 七阶色板预览，仿 FLClash Palette）；
纯黑模式（暗色背景纯黑，Win11 自动关 Mica）。机制：`setTheme/setThemeColor/
setCustomBackgroundColor` 即改即生效即写 `config.json theme` 节；
色块三阶预览公式照抄 `ThemeColor` HSV 变换（所见即所得，有严格一致性测试）。
配色方案变体（M3）与文字缩放按用户确认不移植（无对应物/破坏固定像素几何）。

### 4.9 配置体系（config.json 全键速览，**含各轮新增**）

```
camera{index,width,height,fps,fourcc,backend=MSMF}
tracking{max_num_hands,model_complexity,min_detection_confidence,
         min_tracking_confidence=0.5,bpf,bpf_trigger_misses,bpf_visibility,
         bpf_track_misses,bpf_acquire_every=4,bpf_acquire_backoff_after=40,
         bpf_acquire_max_every=16,bpf_track_crop_factor,bpf_pose_width=256,
         detect_width=960}
activation{hold_ms,max_drift_hs,command_quota,min_drift_norm=0.012}
swipe{…含 direction_invert,home_relative=true}
features{flip,zoom,laser,tap,blackout,nav,spotlight,custom}
cursor{enabled,stream_hz=120,tau_ms=40,ink_hz=60,ink_min_step_px=1.0,ink_tau_ms=30}
face_gate{enabled,check_every=6,absent_disarm_s=9.0}
blackout/ok_exit/pinch{confirm_frames=6}/nav/spotlight/twohand{…}
laser{…,one_euro_min_cutoff/beta,knuckle_min_cutoff=1.2,knuckle_beta=0.8,
      auto_center,auto_center_max_shift=0.15}
zoom{backend,step_scroll_units,hysteresis_*,slide_speed_hs_per_s,
     pan_speed=0.5,pan_deadzone_px=1.5}
tap{max_duration_ms=500,min_dip_hs=0.22,max_lateral_hs,
    freeze_dip_ratio=0.3,freeze_velocity_hs_per_s=2.0}
custom_gestures{enabled,min_points,min_path_hs,stroke_end_frames,
                end_still_ms=400,lost_end_ms=450,end_velocity_hs_per_s=0.5,
                prob_threshold=0.55,dollar_threshold=0.75,dollar_margin=0.03,mapping{}}
screenshot{dir}  countdown{minutes}  pointer_ring{radius}  show_gate{enabled}
demo{ppt_path}                    # 一键演示文稿（第三轮，设置页可选文件）
asr{enabled,mode,energy_threshold,silence_ms,max_segment_s,
    noise_adaptive=true,noise_margin=3.0,translate=true,
    offline{model_type,model_dir}, stream{model_dir,endpoint_silence_s=1.2},
    online{base_url,api_key,model,prompt,segment_s,timeout_s},
    subtitle{font_size=24,max_chars=60}, hotwords[]}
theme{mode=auto,color="#009faa",custom_colors=[],pure_black=false}  # 主题页
calibration{done,ts}              # 校准向导应用后置位（设置页显示"已校准"）
```

---

## 第五部分：工程实践

### 5.1 测试

- 运行：`D:\Anaconda\envs\gesture\python.exe -m pytest tests/ -q`（**当前 419 全绿**；
  套件约 12-15 分钟，后台跑要给足超时）；
- 全部合成 HandFrame / mock 控制层 / offscreen Qt，不依赖摄像头、真 PPT、网络、麦克风；
- conftest.py 自动设 `QT_QPA_PLATFORM=offscreen`；
- **规则**：实测反馈的每个 bug 必须有回归测试；GUI 适配行为有测试锁住；
- 测试里写 config.json 时必须 monkeypatch `CONFIG_PATH` 到 tmp（历史教训）；
- **教训（第二轮新增）**：`pytest ... | tail -2 && git commit` 这种管道会**掩盖 pytest
  退出码**导致带病提交——提交前请直接看 pytest 输出或 `echo EXIT=$?` 确认；
- **教训**：合成手部数据必须**解剖学一致**（指节跟随指尖，否则手型分类按几何规则
  误判，测试会在错误层面失败——多个测试文件有注释示范）；
- **GUI 测试方法论（第四~五轮沉淀，重要）**：
  1. **几何验证必须在真实显示上做**——offscreen 字体度量不同，内容驱动高度不可靠；
     真实显示用普通 QApplication + `w.grab().save('logs/xxx.png')` 截图人工复核；
  2. 自动化测试只断"关系/精确值"（间距=16、对齐、比例、宽度），**不断内容驱动高度**；
  3. 布局嵌套变深后需 `window.show()` 一次，Ignored 尺寸策略才按拉伸比分配宽度；
  4. 动画测试用**条件等待**（轮询 until 条件满足），别用固定时长断言——
     QVariantAnimation 按墙钟插值，事件循环繁忙时固定时长会抖动；
  5. 点击路径回归测试用 `QTest.mouseClick` 走真实事件，别直接调内部方法
     （主题页 _ModeCard 的 clicked 信号事故就是这么漏掉的）；
  6. 主题色/主题是进程级全局状态——测试 fixture 备份恢复（`theme_guard`），
     写 config  monkeypatch `CONFIG_PATH`；
  7. 校准测试合成挥手数据不能每轮重置起点（位移抵消被拒）；手长步计时用
     `wiz._scale_start -= 3.0` 回拨。

### 5.2 打包

`python tools/build_exe.py`（onedir + noconsole；hooks 收集 mediapipe/sherpa_onnx/
sounddevice 资源；config.json 复制到 exe 同级；项目路径不得含中文；打包时剔除其他
conda 环境的 PATH 防抓错 DLL）。产物 `dist/GesturePPT/GesturePPT.exe`。
ASR 模型不进包，首次使用在 exe 旁 `models/` 下载。
**注意：第二~五轮改动后 exe 未重打包（见 6.4 收尾计划）；主题页/深色模式/内嵌校准
向导在 frozen 环境从未验证过。**

### 5.3 常用 CLI 与诊断工具

```
python -m src.cli run / record <名称> / replay <文件> / train / accept [--full]
tools/diagnose_custom_gesture.py   # 自定义手势链路四级体检（样本/训练/分段器/管线）
tools/profile_pipeline.py          # 管线帧耗时探针（avg/p95/max + >100ms 停顿明细）
tools/check_camera.py / check_fps.py / check_qt_modes.py  # 摄像头诊断
```

### 5.4 环境

- conda 环境：`D:\Anaconda\envs\gesture\python.exe`（Python 3.11）
- 依赖：requirements.txt（mediapipe==0.10.18 钉死、opencv、numpy、PySide6、pywin32、
  pyautogui、pytest、pyinstaller、qfluentwidgets、sherpa-onnx、sounddevice）
- 摄像头必须 MSMF+MJPG；**该 4K 摄像头所有模式上限 30fps（实测描述符枚举，
  60fps 宣传不实，报告见 `docs_camera_report.md` 与 `摄像头60fps实测报告.docx`）**。

---

## 第六部分：已知问题、遗留事项与后续方向

### 6.1 当前遗留/挂起事项（**接手者优先读**；2026-09-19 全面更新）

1. **主题页实机问题清单待收集**：第五轮主题页刚落地，用户实测反馈"还有些问题"，
   具体问题点尚未逐条给出——接手后先与用户收集确认，逐个修复并补回归测试。
   我已知/存疑的点（详见 7.5）；
2. **GUI 美化未完成**：布局改版与主题页已完成，但美化大头（设计系统统一、
   页面级打磨）只做了一部分——**详细已做/在想/待办见第七部分 7.4（重点）**与
   `GUI_BEAUTY_PLAN.md`；
3. **exe 未重打包**：第二~五轮全部改动均未进 exe（见 6.4）；主题页/深色模式/
   内嵌校准向导在 frozen 环境从未验证；
4. **cli accept --full 全手势矩阵验收未跑**（用户暂缓，答辩材料需要时再跑）；
5. **深色/纯黑模式实机观感未经用户评审**：深色下卡片是 qfluentwidgets 默认的
   13% 白纱极淡层级，用户机器是亮色系统，深色一直没人真正用过（这轮才修好
   ScrollArea 蒙亮纱的存量 bug）；
6. **摄像头 60fps 不可用**：硬件 30fps 上限（见 5.4），不要再尝试开 60；
7. ~~三个暂缓功能~~（流式字幕/标定向导/一键演示）——**第三轮已全部落地**；
8. ~~A1-A7 实机验证不充分~~——**第三轮已逐项实机验收并修复**（输入电平表、
   字幕条拖动、彩排清除按钮、悬浮窗手位点删除等，均有回归测试）。

### 6.2 设计教训精选（第二轮新增，为什么代码是现在这个样子）

1. **COM 会阻塞到 PPT 主线程空闲为止**——任何周期性 COM 调用都不许上管线线程
   （300-690ms 尖峰 = "画一段直线"的真凶；帧耗时看门狗定位）；
2. **共用一个滤波器实例给两种定位源，切换时必然滑翔**（竖直拖线真凶：指尖/掌根
   共用 One Euro；凡是"手型 A→B 切换导致光标画线"先查共享滤波状态）；
3. **Windows sleep 粒度 15.6ms**：任何依赖 sleep 的高频线程（>60Hz）都必须
   timeBeginPeriod(1)，且插值/定时计算要用真实 dt 而非名义帧率；
4. **Esc 是危险键**：关导航网格用 COM「跳转当前页」（不可能退出放映），Esc 只兜底；
   按键前必须确认目标状态真实存在（G 键回执制）；
5. **"用户说卡"要拆成**：帧耗时尖峰（管线阻塞）/ 输出阶梯（帧率受限）/ 计时粒度失真 /
   滤波滑翔 / PPT 渲染争用——逐层用探针和看门狗定位，不要猜；
6. **合成测试数据要解剖学一致**（指节跟随指尖），否则在错误层面失败；
7. **pytest 输出经管道会掩盖退出码**（见 5.1）；
8. **负样本与拒绝门是识别系统的半边天**（Soli/开集识别/Kazuhito00 一致结论；
   双引擎仲裁 + 距离比门 = 小样本场景的实用上限）；
9. **优先用宿主软件原生能力**（PPT 原生缩放/激光笔/G 键网格/COM），别重造；
10. **可诊断性 > 算法精度**：置信度/判定量/失败原因全部可视化（OctoPocus 思想），
    用户自己就能调。

### 6.3 Phase B：GUI 美化总体设计方案（**部分已执行，剩余见 7.4**）

> 状态（2026-09-19 更新）：**布局改版（1165×720 双态）、主题页、标题栏、灰字统一、
> 页面标题统一、练习/自定义/语音/彩排页细节打磨已完成**（第三~五轮）；本节的设计
> 方法与设计系统仍然有效，但页面级清单大部分已做或被新方案取代——**剩余待办与
> 最新思路以第七部分 7.4 和 `GUI_BEAUTY_PLAN.md` 为准**。6.3.2 的 musepool 插件是
> Kimi Work 的参考检索工具；接手 AI 没有该插件时用 WebSearch 找参考即可，原则不变
> （颜色必须来自参考，不要自造配色）。

#### 6.3.1 目标与边界

- **目标**：在**零行为回归**的前提下，把 GUI 从"功能完整但朴素"提升到"成熟、统一、
  有设计感"，服务答辩演示观感（评委的第一印象）。
- **硬边界（违者必然返工，全是血泪）**：
  1. **窗口固定 1165×720，任何页面/动画/内容不得改变窗口尺寸**；
  2. 卡片多的页一律套 `ScrollArea`（**且必须 `enableTransparentBackground()`**——
     深色主题下默认视口蒙亮纱，第五轮实测修复）；文字全部 `setWordWrap`；
  3. 不动核心链路（管线/检测器/控制层）；美化只动 `src/gui/` 与 `src/overlay.py`；
  4. 每个页面改动独立 commit，改完必跑全量测试 + 手测附录 B 清单；
  5. 沿用 qfluentwidgets 免费版组件体系（不得引入 Pro 复刻版或新 UI 库——SPEC 白名单）。

#### 6.3.2 设计方法（musepool 灵感驱动，勿拍脑袋配色）

1. 先用 musepool 插件广搜参考（`recall --axis`）：方向词如
   "presentation remote control dashboard dark ui"、"camera preview monitoring panel
   layout"、"settings page card grid density"、"status overlay floating widget design"；
   温度 0.4-0.6（工具型产品，不要过度实验）；
2. 选定 1-2 个"惊艳点"深取（`fetch --ref-dim color,typography,layout`），**颜色必须
   来自参考**（主色/背景/文字/强调色四个角色），不要自造蓝紫渐变；
3. 合成时遵守 6.3.3 的设计系统，**只借约束不抄内容**。

#### 6.3.3 设计系统（统一语言，所有页面共用）

- **色彩**（角色化，亮暗主题都要成立）：
  背景层（页面/卡片/浮层三级递阶）、主文字/次文字/弱文字三级灰阶、
  **强调色 = 主题色，用户可在「主题」页自选**（第五轮起；默认 qfluentwidgets 原生蓝
  #009faa，自绘元素一律读 `themeColor()`/`accent_color()`，见 7.3）；
  **状态色语义保持不变**：绿=激活/成功、灰=待机、红=错误、黄/琥珀=警告/练习异常——
  悬浮窗/练习页已用这套语义，全 GUI 统一；
- **栅格**：GAP=16px 统一外边距与卡间距（预览页已建立）；卡片内边距 16-20px；
  同类卡片同宽同高；黄金比例用于主次双栏（自定义页左列：轨迹卡、语音页左区：
  字幕预览 = 1:1.618，均已落地有测试锁住）；
- **圆角与层级**：卡片圆角统一 8px、浮层统一 10-12px；**禁止卡片套卡片**（用留白、
  分割线、字重区分层级；校准向导内嵌模块的三段式子卡是用户特批例外）；阴影能省则省；
- **字体**：标题 TitleLabel、卡题 StrongBodyLabel、正文 BodyLabel、注释 CaptionLabel/
  灰字 四级；数字/英文与中文混排注意 fallback（中文不斜体）；
- **动效**：导航栏开合联动布局插值（300ms 边缩放边移动）+ 校准向导高度动画与
  内容淡入淡出（第四轮新增，同款 300ms 语言）；不新增花哨动效；Toast/InfoBar 复用现有组件；
- **图标**：统一 FluentIcon，不混用 emoji 当图标（现有 ✅/📝 等少量文字符号可保留，
  属于内容而非图标）。

#### 6.3.4 页面级美化清单（逐页执行，每页独立 commit）

1. **预览页**（门面，优先级最高）：摄像头画面与侧栏的等距栅格已好，重点打磨——
   状态卡信息层级（模式大标题+手型/页码/FPS 次级）、功能开关区分组、
   「开始监控」主按钮的视觉重量（主操作唯一高亮）、画面 placeholder 与 16:9 一致性；
2. **手势练习页**：练习目标卡的选择态（当前是蓝边 2px，统一选中语言）、
   三色判定圆点尺寸/间距对齐、统计数字的等宽数字（防跳动）；
3. **自定义手势页**：三步流程的视觉引导（①录制②确认③训练的序号徽章统一）、
   轨迹预览图边框/圆角与摄像头画面一致、已录制手势行卡的删除按钮弱化；
4. **语音识别页**：模式卡/下载卡的进度反馈统一（ProgressBar 样式）、
   热词列表的等宽排版、在线接口表单的标签宽度统一；
5. **彩排统计页（新页，已按规范初版）**：三张卡间距与已有页一致、报告区
   PlainTextEdit 的行高/内边距、导出按钮位置；
6. **设置页**：SpinBox 对齐列（数值列等宽）、分组小标题（阈值/工具箱/路径 三组）；
7. **日志页**：等宽字体确认、滚动条样式、刷新时的滚动位置保持；
8. **悬浮窗**（演示时评委看得见，重点）：整体圆角/边框/透明度与主 GUI 同语言、
   缩略图 16:9 严格、备注区/识别胶囊/站位引导的视觉融合（A2/A3/A5 新加元素要
   统一进同一套悬浮窗视觉）；
9. **浮层**（字幕条/备注大字卡/倒计时/指针环/聚光灯）：圆角、透明度、字号的统一
   （字幕条 A4 已重做，其它浮层向它对齐）。

#### 6.3.5 美化验收标准（交付前必过）

1. 全量测试 419+ 全绿（含窗口尺寸回归测试覆盖全部九页）；
2. 手测附录 B 清单：开合导航栏窗口不变、九个页面逐个点开、监控启停正常；
3. 亮/暗主题切换各检查一遍（「主题」页切换），**深色下重点看卡片层级与自绘元素**；
4. 与美化前截图对比：无内容错位、无文字溢出、无卡片挤压；
5. 用户目测确认（用户对美观有一票否决权）。

### 6.4 收尾计划（Phase B 之后，答辩前）

1. **全量测试**：419+ 全绿；`cli accept --full` 如需答辩量化数据则现场配合跑；
2. **exe 重打包**：`python tools/build_exe.py`，产物 `dist/GesturePPT/GesturePPT.exe`，
   在无 Python 环境的干净机器上验证（重点：人脸门控、插值线程、COM 轮询在 frozen
   环境下正常；`sys._MEIPASS` 路径兼容此前已处理）；
3. **答辩彩排**：按 `DEMO.md` 脚本走 2-3 遍全流程（激活→翻页→缩放→激光笔书写→
   导航→自定义手势→字幕/翻译→备注提词→彩排统计页导出报告），更新 DEMO.md 把
   A1-A7 的新演示点加进去（建议把"彩排统计报告"作为答辩收尾的量化亮点展示）；
4. **文档收尾**：README 更新（九页导航/新功能/新配置键）、HANDOVER 最终版。

### 6.5 给接手 AI 的工作建议

- 先读 `AGENTS.md`、`SPEC.md`、`README.md`，再读本文件；改任何手势逻辑前先跑
  `pytest tests/` 确认基线全绿（当前 419）；
- **实测反馈驱动**：涉及手感/延迟/识别率的改动，主动给出可复现的实测路径
  （`tools/profile_pipeline.py` 探针 + worker 帧耗时看门狗日志已是现成工具）；
- 用户非常重视 UI 观感与**适配铁律**（4.8 节十二条，尤其窗口尺寸）；
- 新增依赖/网络功能：先问用户，批了改 SPEC 再动手；
- commit 信息用中文、说清"实测反馈"来源（项目历史习惯）；
- 每个修复独立 commit 便于 `git revert`；关键版本建议打 tag。

---

## 第七部分：第三~五轮改动全录与 GUI 美化计划（2026-09-14 ~ 09-19，**接手重点**）

> 本部分是 v2.1 新增，记录第三轮~第五轮（Kimi Code）的全部改动、设计决策与教训，
> 以及**未完成的 GUI 美化的完整思路与计划**。接手 AI 请先读 7.4/7.5，再回读细节。

### 7.1 第三轮（2026-09-14）：A1-A7 验收修复 + 三个暂缓功能落地

**A1-A7 逐项验收结果**（用户实测 + 我复查）：
- **A1 噪音自适应 VAD**：逻辑复查通过（用户附近无嘈杂环境，靠测试与代码审查验证）；
- **A2 置信度可视化**：用户实测无问题；
- **A3 备注提词**：复查通过（用户此前未测过）；
- **A4 字幕条**：①实测"鼠标想拖动但拖不动"——根因是字幕条挂了
  `WA_TransparentForMouseEvents`，已修（去掉透明穿透 + 拖拽 + 用户拖动位置记忆，
  有测试）；②"中文字幕下出英文小字"（在线翻译）因用户还没配百炼密钥未实测，
  我做了代码级复查（双行切分/热词只矫正中文行/英文限长防溢出）——**实际联网效果
  待用户配密钥后验证**；③**离线语音识别"完全没反应"深挖**：用户麦克风
  （XIBERIA K03S）底噪 RMS≈0.01，恰压在 `energy_threshold=0.01` 上导致永远切不出
  语音段——无法区分是麦克风、阈值还是模型问题。修复：语音页加**输入电平表**
  （快攻慢放动画 + 峰值驻留刻标 + 琥珀色阈值标线 + 设备名显示），可诊断性一目了然；
- **A5 手位小点**：当时改为"没识别到手时消失"（**第四轮用户又决定整个删除**，只留
  识别区虚线框）；
- **A6 彩排统计**：报告卡、累计统计卡各加「清除」按钮（有回归测试）；
- **A7 人脸门控**：评价为"保险而非刚需"，保留。

**三个暂缓功能全部落地**：
1. **流式字幕第三模式**：sherpa-onnx `OnlineRecognizer.from_zipformer2_ctc`，模型
   `models/zipformer_ctc/`（21.3MB，**ghproxy.net 镜像下载——GitHub 直连超时教训**）。
   `src/asr/streaming.py` StreamingEngine（accept_waveform 喂帧/endpoint 检测/reset）；
   manager 加 `partial_ready` 信号 → 字幕条 `set_partial`（占"当前句"位、尾随光标
   表示未定型）；句尾停顿 1.2s（`asr.stream.endpoint_silence_s`）自动定稿；
   识别模式 UI 三选一（离线/流式/在线），模式卡槽只显示当前模式的模型卡；
2. **手势灵敏度标定向导**：测量器在 `src/calibration.py`（HandScaleMeasurer/
   SwipeMeasurer/HoldMeasurer + `compute_suggestions` **clamp 只放宽不收紧**——
   绝不在用户数据好于默认时收紧阈值，保护原有准确率）；设置页加入口；
3. **一键演示**：`ppt_com.launch_and_start_show(ppt_path)`（GUI 线程自建 COM 连接），
   config `demo.ppt_path` 默认 demo.pptx（设置页可换），文件不在则复用 PowerPoint
   当前打开的文稿。

**其它第三轮改动**：手势说明从预览页弹窗搬为独立导航页「手势说明」；
**首次启动报错修复**：`SubtitleOverlay._partial` 原先不在 `__init__` 初始化，
paintEvent 引用即 AttributeError——而 **PySide6 会吞噬 paintEvent 异常**并刷一堆
`QPainter`/`QBackingStore` 报错（用户首次启动日志实锤），有测试直接调
`paintEvent(None)` 守护。

### 7.2 第四轮（2026-09-15 ~ 09-17）：1165×720 布局改版 + 细节打磨

**窗口与预览页双态布局**（用户逐像素亲定，我核算闭合）：
- 窗口 **1165×720**（黄金比例），标题栏 48，内容区 672；导航收起 48 / 展开 **165**；
- 收起态：画面 **760×428**、侧栏 **270**；展开态：画面 **675×380**、侧栏 **250**；
  核算：35+760+36+270+16=1117=1165−48 ✓ / 165+29+675+30+250+16=1165 ✓；
- 导航动画逐帧插值 `apply_blend`（**绝不可删**）；顶/底边距由居中出现（用户"72"的
  真实意图 = 与侧栏边距一致，不写死）；
- 功能开关两列四行（补上漏展示的"自定义"复选框）；侧栏序列：状态卡（内容驱动）→
  开关卡 179 → 校准向导/开始监控/一键演示 各 56px，间距全 16，上下边距 53。

**校准向导内嵌预览页**（对话框版退役删除）：`WizardPanel` 三段式子卡（步骤引导/
测量结果+进度条/操作列含停止）+ `InlineWizard` 高度动画（**必须逐帧 setFixedHeight**——
maximumHeight 动画会被内容 sizeHint 截短）+ `preview_page.on_blend` → `sync_height`
跟随导航；打开自动开监控；`pipeline.calibration_active` 屏蔽一切识别；悬浮窗活动行
显示"校准中"；关闭/停止丢弃全部测量。09-17 又加**内容淡入淡出**（QGraphicsOpacityEffect
作用于内容容器：打开先空白展开、展开完内容才淡入；关闭先淡出成空白再收起；
快速 toggle 时停掉进行中动画——`stop()` 不发 `finished`，挂接动作自动作废）。

**标题栏定制**（`src/gui/title_bar.py`）：左上系统名改「**Sylthos**」（用户新定的
系统名）——显示数学粗斜体字形 𝑺𝒚𝒍𝒕𝒉𝒐𝒔（**码位必须从用户原文提取**：U+1D47A/
1D49A/1D48D/1D495/1D489/1D490/1D494，第一版凭记忆写错渲染成方框+ypxlow）+ 17px 粗体；
任务栏保持纯文本 Sylthos。局部 qss **追加式**写入（`setTheme` 会重刷 CaptionLabel 的
LABEL qss 覆盖自定义字号——挂主题信号重补，见 7.3 信号时序）。右上三按钮满高
46×48（原 46×32 顶对齐，hover 只盖上半）：按钮图标按 32 高硬编码，用**事件过滤器
接管 Paint**（背景满高、图标在居中的 32 高区按原坐标绘制），保留原按钮对象
（qss 主题色/信号/拖拽区域不受影响）。

**各页细节打磨（用户逐页验收反馈驱动，全部有回归测试）**：
- 注释灰字统一 `color:#888`（练习/自定义/语音/彩排/说明页）；
- 页面标题与导航名统一：「设置」「彩排统计」「手势说明」「语音识别」「自定义手势」
  （去掉括号后缀；**改名不改字号**——TitleLabel/StrongBodyLabel 类不变）；
- 自定义页：步骤序号 ①②③；**黄金比例重排**——左列 = 录制卡 237 + 间距 6 + 训练卡 77
  （= 确认卡高 320，顶对齐、底对齐、间距=原页面间距 6），左列：确认卡 = 1:1.618
  （实测收起 1.6165/展开 1.6185）；绑定指令下拉 `setMaxVisibleItems(10)` 限高滚动
  不伸出窗口；「尚未录制」上移到标题行且横向不动（**用固定宽标题列 448+6 对齐**——
  按 sizeHint 反解间距会在字体抛光后漂移 7px，教训）；训练卡单行纵向居中（实测
  332≤349 放得下，文案没缩短）；
- 语音页：四模块 2+1+1 排版（启用|模式 / 模型槽整宽 / 电平整宽），左区：字幕预览 =
  1:1.618（Ignored 尺寸策略防内容顶歪比例）；模式框按钮只显示短名（离线/流式/在线
  识别）、下拉项保留完整文案（`currentIndexChanged` 在 `setText` 之后发射，后手覆盖
  按钮文字即可）；热词列表加高 140/220；
- 彩排统计页：累计统计卡加高（120/160→180/260）、空态提示改占位灰字；
- 设置页：`_NoWheelSpinBox`（wheelEvent ignore → 事件上传滚动区，防滚动浏览时误改
  数值）；新增 8 个可调项（带倍率显示：activation.max_drift_hs ×100 等）；
  旧 config 缺键跳过（向后兼容不崩页）；
- 日志页：只有已在底部才跟随新日志回弹 + 等宽字体（`setPlainText` 会把滚动位置
  重置到 0，需先记再恢复）；
- 预览页：悬浮窗手位小点删除、状态圆点删除（`status_dot.py` 退役）。

### 7.3 第五轮（2026-09-19）：主题页（仿 FLClash）与主题机制深挖

**调研**：精读 FLClash 仓库（github.com/chen08209/FlClash）主题系统
（`lib/views/theme.dart` / `widgets/color_scheme_box.dart` / `widgets/palette.dart` /
`models/config.dart`）。其主题页四模块：主题模式三选卡、主题色网格（**色块=该种子色
的三色方案预览**而非单色、首块默认色带角标、+自定义 HCT 取色器、长按删除、重置）、
纯黑模式、文字缩放；机制 = Material 3 `ColorScheme.fromSeed`（一种子色 → HCT 空间
5 条色调板 → ~30 个语义角色色，全 app 只读角色色）。

**映射决策（用户逐项确认）**：主题模式→`setTheme(AUTO/LIGHT/DARK)`；主题色→
`setThemeColor()`（qfluentwidgets 自带一种子色→7 阶 HSV 色板）；纯黑→
`setCustomBackgroundColor`（Win11 关 Mica）；**放弃 M3 方案变体 9 选 1**
（qfluentwidgets 色板公式固定无对应物）与**文字缩放**（Qt 无全局缩放，会破坏固定
像素几何）；预设色沿用 FLClash 审美但**纯黄换橙**（纯黄做 UI 主色太刺眼）。

**实现**（`src/gui/theme_page.py`）：`_ModeCard`（选中主题色描边）/ `ColorTile`
（84px，64px 全圆角三阶预览 = 上 PRIMARY 下 LIGHT_1/DARK_1，选中描边+中心√，
hover 60% 描边，默认角标）/ `ColorTileGrid`（自适应列数）/ `GradientSlider`
（24px 全圆角渐变轨道+白边高光+6×48 竖条 thumb，仿 Palette 滑条）/ `ToneGrid`
（11 档明度，数字标签深底白字，选中主题色外环）/ `PaletteDialog`（HSV/HSL 近似
HCT：色相/彩度滑条+明度网格+七阶预览）/ `ThemePage` / `apply_theme_settings`
（启动时应用，**须在标题栏定制前完成 setTheme**）/ `apply_pure_black` /
`accent_color(dark_canvas=)` / `theme_palette`（阶色公式照抄 ThemeColor，所见即所得，
有严格一致性测试）。改动即写 `config.json theme` 节即生效。

**深挖出的三个存量/库级发现（qfluentwidgets 1.11.3，全部已修并有测试）**：
1. **ScrollArea 没有 qss、默认视口用系统调色板（恒亮白）**——深色主题下内容区蒙
   亮纱（此前深色从没人真用过，主题页实测才暴露）。修法：`_scrollable()` 统一
   `enableTransparentBackground()`（适配铁律第 13 条）；
2. **`setThemeColor` 只发 `themeColorChanged`，且发射在 `updateStyleSheet` 重刷之前**；
   `setTheme` 发 `themeChangedFinished`（重刷之后）。换色跟随钩子必须**双挂两个信号**；
   会被重刷覆盖的自定义样式（Sylthos 标题字号）要**推迟一轮事件循环**补写
   （`QTimer.singleShot(0)`）（适配铁律第 14 条）；
3. **暗主题下 ThemeColor.PRIMARY 也会被提亮**（s×0.84, v=1）——预览/取色公式勿直接
   用种子色。

**主题色传播面**：qss 占位符（line_edit/slider/spin_box）+ Python 绘制（switch/
checkbox/nav/buttons/info_bar）自动跟随；自绘元素逐个改读主题色（字幕条英文小字/
轨迹线/悬浮窗工具模式色+备注区/练习页目标卡描边/电平条未超阈值填充——恒深底一律
`accent_color(dark_canvas=True)` 提亮变体）；**语义色不动**（绿成功/红失败/琥珀警告/
灰注释——与 FLClash 一致）。

**实测事故**：`_ModeCard` 曾把 CardWidget 内置无参 `clicked` 重定义为 `Signal(str)`，
基类 `mouseReleaseEvent` 无参 `emit()` 每次点击抛 TypeError（适配铁律 6 变体，
已补案例；回归测试改 `QTest.mouseClick` 真实点击路径——直接调内部方法测不出来）。

### 7.4 GUI 美化：设计哲学 / 已完成 / 待办（**本阶段主线，最重要**）

**设计哲学（每次动手前默念）**：
1. 铁律不变：窗口 1165×720、零行为回归、每页/每批独立 commit、全量测试绿、
   **真实显示截图复核**（offscreen 字体度量不同，内容驱动高度不可靠）、
   亮暗双主题都查、**用户对美观有一票否决权**；
2. 色彩角色化：强调色 = 主题色（用户主题页自选，默认 #009faa）；状态色语义固定
   （绿成功/红失败/琥珀警告/灰注释）；中性三级灰阶；**颜色来自参考不自造**；
3. Fluent 2 token：圆角 按钮 4 / 卡片 8 / 浮层 12；暗色层级靠亮度不靠阴影；
   字体 ramp 用语义 Label（TitleLabel/StrongBodyLabel/BodyLabel/CaptionLabel），
   少直写 `font-size`；
4. 栅格：模块间距 16（2×8）；黄金比例只用于主次双栏（已落地：自定义页、语音页）；
5. 动效只用已有语言（300ms 边缩放边移动 + 淡入淡出）；不引入第三方主题/Pro 组件；
6. 测试只断"结构/关系/精确值"（对齐、间距、比例、类名、钩子存在性），**不断具体
   色值与内容驱动高度**（防脆弱测试）。

**已完成（第三~五轮，全部有 commit 与测试）**：窗口 1165×720 黄金比例双态布局；
预览页侧栏序列；功能开关 2×4；校准向导内嵌+淡入淡出；标题栏 Sylthos+按钮满高；
注释灰字统一；页面标题统一；自定义页/语音页/彩排页/设置页/日志页细节打磨（见 7.2）；
主题页+全 app 主题色跟随（见 7.3）；状态圆点/手位小点精简。

**待办清单**（详见 `GUI_BEAUTY_PLAN.md` B1~B7，按建议顺序；每批独立 commit +
双主题截图复核 + 用户验收后下一批）：
1. **主题页实机问题修复**（最优先——用户实测反馈"还有些问题"，清单待收集，见 7.5）；
2. **B1 剩余**：恒深底浮层（字幕条/悬浮窗/轨迹图黑底）在亮主题下的协调度评审——
   先让用户看深色实机再定要不要给浮层做亮主题浅底变体；
3. **B2 状态色语义统一**：练习页判定色（#22c55e/#ef4444/#eab308）、电平条青绿、
   悬浮窗活动行琥珀、向导进度条 对齐同一套色板；
4. **B5 主按钮语义化**：每页唯一主操作换 `PrimaryPushButton`（主题色填充）——
   预览页「开始监控」、自定义页「开始录制」、语音页「开始识别」；注意别动按钮尺寸；
5. **B6 设置页分组小标题**：19 项按语义分组（手势阈值/语音/演示工具）解决平铺感；
6. **B3 圆角 token 统一**：自绘浮层（字幕条/悬浮窗/Toast/备注大字卡）圆角对齐 12；
7. **B4 直写字号清理**：盘点 `font-size:` 直写处（向导子卡 12px、语音注释 12px、
   练习页圆点 18px 等），能换 CaptionLabel 的换，保留的注明理由；
8. **B7 间距栅格审查**：零散 4/6/8/14px 能归 8 倍数则归（**用户亲定的值一律不动**，
   注释注明）。

### 7.5 当前已知问题与风险清单（接手后先读）

1. **主题页实机问题待收集**：用户实测反馈"主题还有些问题"但具体点尚未逐条给出——
   接手第一件事找用户对齐清单，逐条修复 + 补回归测试；
2. `QFont::setPointSize: Point size <= 0 (-1)` 启动警告：Qt/qfluentwidgets 库噪音
   （2026-09-14 日志就有，早于主题页），无害未修；
3. exe 未重打包；主题页/深色模式/内嵌校准向导在 frozen 环境从未验证；
4. 深色/纯黑实机观感未经用户评审（深色卡片是库默认 13% 白纱极淡层级）；
5. 主题页「+」加色块是普通 PushButton("+")，不如 FLClash 的 tonal 图标按钮精致
   （可选美化点）；
6. `_ModeCard` 右键也会触发模式切换（CardWidget.clicked 不分按键）——小瑕疵，
   用户在意再修（mouseReleaseEvent 里判 button 即可，但注意别覆盖 clicked 信号）；
7. 标题栏 label 的 stylesheet 在多次换主题色后会累积重复的 `FluentLabelBase` 规则
   文本（qfluentwidgets 重刷的库行为，仅文本冗余无视觉影响）；
8. ComboBox 下拉弹层（RoundMenu）在自定义主题色下的配色未逐一核对；
9. 在线语音（百炼）"中文字幕下英文小字"：用户未配密钥从未联网实测（第三轮代码级
   复查过逻辑）；
10. 亮色主题下恒深底浮层（字幕条/悬浮窗/轨迹图）协调度未评审（B1 剩余）。

---

## 附录 A：关键文件与接口速查

| 要做什么 | 入口 |
|---------|------|
| 加新手势（规则类） | `src/gestures/` 新建检测器 → `pipeline.py` 加进 detectors → `decision.py` 加 GestureType/_ALLOWED/FEATURE_OF |
| 加新指令（自定义手势可绑） | `pipeline.py` `_CUSTOM_COMMANDS` + `_CUSTOM_COMMAND_LABELS` + `custom_gesture_page.py` `COMMAND_CHOICES`（有测试防漏加） |
| 加新浮层 | `src/overlay.py` 新建类（跟随类用 `FollowSmoother`）→ `worker.py` 加信号桥接 → `overlays_mixin.py` 接线 |
| 加新 GUI 页面 | `src/gui/` 新建页 → `fluent_window.py` addSubInterface（套 `_scrollable`，**内含透明背景**）→ 窗口尺寸回归测试加页面清单 |
| 改主题/主题色/纯黑 | 「主题」页或 `config.json` theme 节；自绘元素取色用 `theme_page.accent_color()` |
| 改校准流程/阈值建议 | `src/gui/wizard_inline.py`（内嵌模块）+ `src/calibration.py`（测量器/建议逻辑） |
| 改一键演示文稿 | 设置页「一键演示文稿」或 `config.json` demo.ppt_path |
| 改标题栏 | `src/gui/title_bar.py`（Sylthos 字形/字号、按钮满高绘制过滤器） |
| 改阈值 | `config.json` 或设置页（热更新生效；设置页 SpinBox 已禁滚轮防误触） |
| 改光标手感 | `config.json` cursor.*（tau/ink_hz/ink_tau/min_step） |
| 改语音模式 | `src/asr/`（离线引擎接口 `ASREngine.transcribe(segment)`；流式引擎 `StreamingEngine` 是另一套流式接口） |
| 打包 | `python tools/build_exe.py` |
| 卡顿定位 | `tools/profile_pipeline.py` + logs/app.log 搜"帧耗时尖峰" |
| 自定义手势诊断 | `tools/diagnose_custom_gesture.py` |

## 附录 B：验证清单（交付前必做）

1. `D:\Anaconda\envs\gesture\python.exe -m pytest tests/ -q` 全绿（**注意退出码，勿用管道掩盖**）；
2. GUI 启动：`D:\Anaconda\envs\gesture\python.exe -X utf8 -m src.main`，
   开合导航栏窗口尺寸恒为 1165×720，九个页面逐个点开；
3. 涉及识别链路的改动：实机走一遍"激活→手势→执行→自动退出"；
4. 涉及光标/浮层的改动：实机验证指向/书写/平移/聚光灯四路手感（丝滑专项标准）；
5. 涉及主题/配色的改动：**亮/暗/纯黑三态各截一遍真实显示图**核对（自绘元素、
   卡片层级、标题栏 Sylthos 字号存活）；
6. git commit（中文信息，说明实测依据）。

---

*本文档最后更新：2026-09-19（v2.1），对应第五轮（主题页）完成。当前状态：全部既定
功能 + 三个原暂缓功能（流式字幕/校准向导/一键演示）落地，GUI 布局改版与主题页完成，
**GUI 美化进行中（第七部分 7.4 是接手重点）**，收尾（exe 重打包 + 答辩彩排 +
DEMO.md 更新）未做。*


## 2026-10-06 接手补充：选中框修复与全局主题配色

本节覆盖前文主题配色实现的旧说明；识别与控制链路未改动。

- 用户实测：第二个色块选中后，第一个框仍残留。根因是布局移除不等于控件销毁。
  `ColorTileGrid.set_tiles` 立即隐藏旧控件，再 `deleteLater`，避免绘制重影与点击遮挡。
  独立提交 `d1dd0a9`；该阶段全量 421 项通过。
- 修改前已创建带注释的 Git 存档 `v1.5-pre-theme-refinement-20261005`，指向
  `735cbfca5bb738fe56935a824029dd3eb7c702e5`。回退时先保存后续工作，再按该标签恢复。
- 新入口 `src/gui/theme_style.py`：种子色派生窗口、内容面、卡片、输入框、选中容器、
  强调色与文字等角色。应用卡片继承 Fluent CardWidget，保留布局/点击/动画接口。
  主题控制器在库刷新 QSS 后合并应用配色；不参与识别帧循环。
- 预览、练习、录制、语音、彩排的主操作使用实色主按钮；其他按钮用柔和容器色。
  主题模式与练习目标卡增加选中底色；导航选中背景同步。预览色块/取色对话框展示新角色。
- 为保证背景色可见，窗口统一关闭 Mica；纯黑只影响深色窗口和内容底，卡片仍保留层次。
  原始 seed 继续保存到 config/qconfig，Fluent 内置开关和恒深色画布保持原有派生强调色。
- 参考 FLClash 的色彩角色分工，使用 Qt HSL 与最终 8 位色对比度约束实现。
  **不是 Flutter Material 3 的 HCT 算法复刻**，未引入新依赖。
  参考源码：
  https://github.com/chen08209/FlClash/blob/main/lib/providers/state/theme.dart
  https://github.com/chen08209/FlClash/blob/main/lib/widgets/color_scheme_box.dart
- 回归测试：真实点击后只留一份选中态/控件；预设与黑白灰黄自定义色的文字对比度；
  浅/深切换时检查卡片内部和主按钮像素确实变色；纯黑开关与窗口尺寸。
  渲染测试使用独立 pytest 子进程，隔离其它测试遗留窗口的延迟删除和全局 Qt 信号。
- Windows 实窗验证使用临时配置：已逐一打开九个页面，检查导航展开、浅/深/纯黑与
  藕粉→紫色选中框切换。未启动摄像头、麦克风或 PowerPoint。
  验证窗口标题为 Sylthos Theme QA；产品标题相关测试仍验证原 Sylthos 字号。
- 后续审美调整建议先让用户体验本轮整体换色，再确定彩度和表面对比强度；
  不与识别算法优化、版式大改同时进行，便于判断偏好与回退。

- 最终验证：`python -B -m pytest tests/ -q -p no:cacheprovider --basetemp=<可写临时目录>`，447 passed（253.19s）；`git diff --check` 通过。


## 2026-10-06 用户实测补充：目录、标题、灰字与短暂残框

- 原目录 `D:/Kimicode/Gesturerecognition` 的 master 仍为 `735cbfc`，有用户自己的
  config.json 修改；本轮没有覆盖或同步该目录。工作副本基于同一提交，位于
  `C:/Users/12097/.codex/worktrees/b870/Gesturerecognition`。
  `python -m src.main` 取当前目录的 src，交付必须同时给出切换目录的命令。
- 上轮临时验证脚本调用 setWindowTitle('Sylthos Theme QA')，覆盖了花体标签显示。
  产品 title_bar.py 未修改；今后视觉验收脚本不得重设窗口标题。本轮实窗已确认原花体。
- 用户认可柔和配色，保持不变。普通换色不再重建色块：原位更新选中态，清除 hover，
  在全局 QSS 刷新前 repaint；只有增删自定义色才重建，并立即隐藏旧控件。
  hover 改成内部提亮，避免像第二个选中外框。默认角标在亮暗切换时同步更新。
- 灰色说明文字使用 FluentLabel.setTextColor 保存亮暗两套 #888888，避免全局样式
  更新把临时 setStyleSheet 的灰色覆盖成黑/白。保留原来的初始局部样式与布局。
- 回归新增：进入全局换色之前旧选中态已清除、悬停不产生选中外框、结构重建立即隐藏旧项；
  渲染回归增加多次亮暗/颜色切换后的灰字实际 palette 与花体标题/17px 检查。
- 本轮修改前存档：`v1.6-pre-theme-feedback-20261006`（`af2c39d`）。
- 最终验证：450 passed（242.41s），git diff --check 通过；真实窗口浅色/深色/纯黑均保留花体标题和灰色注释。


## 2026-10-06 追加实测：主题卡一致性、语音布局、自定义页顶部对齐

- 修改前存档 `v1.7-pre-layout-feedback-20261006`，本轮继续独立副本开发，未同步原目录。
- 再次只读比对原目录：master 为 `735cbfc`，仅 config.json 有用户修改。
  语音布局结构与本副本一致。离屏几何探针在两份代码均复现：换色会丢失临时
  12px QSS，字号回到 14px；说明换行和导航变窄都会改变顶行高度。
  此结论限当前环境复现，不推断用户此前环境/数据完全相同。
- 补齐语音页遗漏的 #8a8a8a 注释：使用 setTextColor 持久保存颜色；通过
  pixelFontSize 属性持久保存 12px 字号。模型介绍、输入电平说明、接口字段等均覆盖。
- 语音页换行标签按标准窗口窄列正文宽度 330px 预留高度；导航开合时保持顶行各卡
  上下边界，窗口更窄或动态文本更长仍可重新计算高度，不裁掉说明。
  本机离屏对比：电平卡始终 134px、预览卡始终 366px（默认离线、未加载模型）；
  这些值只作诊断记录，测试断相对稳定性，不写死跨环境像素值。
- 默认色不显示重置按钮，但保留其布局占位，使主题色卡高度不随选择变化。
  删除默认色独有的色盘角标，默认身份保留在悬停提示；「+」统一 64×64、16px 圆角。
- 自定义手势页只给顶层布局设置 AlignTop：标题、原录制/训练/确认模块、列表标题、
  数据行依次紧随。保留 448×252 轨迹图、320px 操作区、原录制/筛选/训练/映射逻辑。
  列表仍使用原来的外层 ScrollArea，多条样本自动扩展并滚动。
- tests/test_layout_feedback.py 在隔离窗口覆盖：默认/其他主题色卡同高、无孤立角标、
  加色按钮圆角；亮暗/三识别模式中反复开合导航的各卡高度与位置；灰字和字号不丢；
  自定义页标题与语音页对齐，操作区/列表紧随，18 个临时样本组可滚到最后一组。
- 最终验证：451 passed（268.52s）；git diff --check 通过。实窗检查默认/非默认色卡同高、圆角、语音页导航开合、自定义页对齐，以及浅/深/纯黑三态。

## 2026-10-07 阶段A首批：用户批准总计划，等待人工手感验收

- 当前执行入口为 IMPLEMENTATION_PLAN.md；旧 PLAN.md 已标为历史规划。用户要求在需要人工验证时暂停，等待结果。
- 修改前标签 v1.8-pre-stage-a-20261007 指向 dd1eadb。工作区原有 config.json 在项目外 stage-a-baseline/worktree-config.json 备份，未改动、未提交、未同步原项目。
- A1：帮助页平移手型改为食指；导航说明明确 OK 退出。回归同时检查帮助内容与实际模式／平移行为。
- A2：练习达标判断先保存旧的已学会状态；自动推进后重绘所有行，清除旧选中框。回归覆盖第4→5次、重复旧动作、全部完成与清零。
- A3：删除掌根滤波器第二次初始化，恢复 knuckle_min_cutoff/beta 参数；维持指尖与掌根独立。回归覆盖默认值、专用参数、热重载及独立历史；原书写过渡冻结用例通过。
- 基线451项通过；5项新回归均在修复前按预期失败，修复后连同书写过渡、热重载13项通过。全量结果见后续记录。
- 人工验证步骤见 STAGE_A_VALIDATION.md；需要验证慢画／快画／停笔／切换手型及练习自动推进。没有宣称实机手感已改善。
- A4数据表述与独立验证、视觉和动效尚未实施；保留训练集准确率的用户决定不变，先视觉后动效的顺序不变。

- 最终全量：456 passed（249.35s）；git diff --check通过。独立提交：A1 efac0f0、A2 7b86ec0、A3 b5debd7。当前停在人工验证关口，不继续A4或GUI改版。


## 2026-10-07 预览实测反馈：圆角、导航缩放、文字抖动

- 用户确认阶段A前三项人工验证通过。随后发现摄像头图像没有圆角、导航变大时留旧尺寸和偏左画面、提示文字轻微抖动。
- 基线735cbfc中同样是QLabel样式圆角和_on_frame中预缩图；近期主题与阶段A提交未修改这两个路径。样式背景圆角不会裁剪图像；预缩图直到下个摄像头帧才随容器变化。
- 修复：CameraPreview绘制原分辨率QImage，每次paint按当前尺寸等比居中、圆角裁剪，导航动画即使没收到新帧也重绘；保留760×428／675×380尺寸与导航时长，不改识别线程。
- 提示文字保留独立固定尺寸子控件；页面布局激活后在页面坐标单次取整，避免奇数高度时两次居中取整造成1px上下跳动。带向导时仍在画面内居中。
- 新增tests/test_camera_preview_feedback.py：双向缩放无新帧、四角裁剪、奇偶高度文字位置、4:3画面等比居中。修复前4失败1通过，修复后专项与原窗口布局36项通过。
- 修改前存档v1.9-pre-preview-feedback-20261007；人工复测见PREVIEW_VALIDATION.md。实窗模拟程序已启动但Windows窗口工具无法列出，未完成实窗验收，不用离屏测试替代用户观感。

- 预览修复最终全量：461 passed（254.98s），git diff --check通过。自动化完成，等待真实摄像头观感验证。


## 2026-10-07 A4数据口径与B0视觉候选

- 用户确认预览修复通过。A4保留accuracy字段与原计算方法，明确training口径；报告新增n_recorded_samples/n_generated_samples/accuracy_scope，各类计数不再包含因点数不足被跳过的文件。
- 训练Toast显示训练集准确率及两类样本数；状态标签保留百分比，悬停解释新动作／陌生人尚未独立测试。独立评估仍按阶段D实现。
- 彩排导出与累计统计改称指令分发并注明未确认PPT外部执行。worker保留command_executed历史信号名，只纠正注释，不改控制链路。
- tests/test_metric_semantics.py覆盖有效样本数、GUI保留准确率与未测试说明、导出口径。
- GUI_B0_PROPOSAL.md为待审候选，示意图在本会话visualizations目录，未修改实际预览／设置页布局。等待用户审美评审。

- A4最终验证：464 passed（255.68s），git diff --check通过。暂停在B0候选设计评审，原项目未同步。


## 2026-10-19 用户批准方向并细化三页

- 最新要求覆盖旧B0草图：设置标题下不放注释，常用参数各自独立卡片，工具唤起／退出全部直列；仅专业参数可折叠。功能开关只缩标题，保持控件原大小及居中。状态卡保留模式、手型、页码、FPS。自定义列表上方增加少量留白。
- 本批实现：状态卡153px高度保留，模式用SubtitleLabel；两模块标题用StrongBodyLabel；功能开关网格仍24px列距、179px卡高，弹性留白居中。
- 设置保留全部原ITEMS、范围、倍率、保存和热重载回调。增加分组标题；专业参数采用240ms高度＋120ms淡入，关闭时反序；停止旧动画后从当前高度／透明度继续。内容行用普通Widget避免卡片套卡片。
- 自定义列表前增加20px间隔；更新旧布局回归中的间距要求，多数据滚动仍检验。
- 新增tests/test_gui_refinement.py；定向34项通过。Windows平台渲染检查了亮／暗的预览、设置开合、自定义页面，未启动真实摄像头／PPT。
- 存档v1.11-pre-gui-refinement-20261019。待人工验证步骤和额外设置候选见GUI_REFINEMENT_VALIDATION.md；未添加新配置项，原项目未同步。
- 本轮专业参数动效由用户明确要求随模块实施，不代表提前开启全局阶段C。完成后暂停等待人工审美及动画反馈。

- 最终全量466 passed（247.06s），git diff --check通过。当前暂停在本批人工验收，未同步原项目。


## 2026-10-19 反馈调整：独立专业参数与摄像头选择

- 本条覆盖之前的专业参数折叠方案：三个参数恢复为与其他设置相同的独立 CardWidget，直接显示，删除不再使用的折叠组件。
- 新增设置仅 camera.index，保留原有摄像头分辨率、帧率、后端等配置。按 OpenCV 编号选择，不把 Qt 设备列表顺序误当作 OpenCV 编号，也不自动开启摄像头探测。
- 摄像头编号保存后，下次开始监控时使用；不触发当前检测管线重载，不中断演示。页面灰色提示明确生效时机。
- tests/test_gui_refinement.py 将折叠动画测试替换为三张独立卡片的层级、可见性、高度和边距回归；补充摄像头编号保存、重新打开、其他摄像头配置保留、不触发热更新的测试。
- 修改前存档：v1.12-pre-camera-selection-20261019。继续在独立副本中修改，原项目未同步。

- 本轮验证完成：定向37项通过，全量469 passed（270.16s），git diff --check通过；已检查Windows平台亮／暗设置页渲染。真实设备切换与最终观感等待人工验收。


## 2026-10-19 摄像头名称下拉选择（覆盖编号输入方案）

- 用户要求删除摄像头行注释，使用本机摄像头名称下拉列表；没有设备显示“无”。已落实，样式沿用其他设置行。
- 引入 cv2-enumerate-cameras==1.4.0，按当前 DSHOW/MSMF 后端枚举名称及索引；ANY 优先 MSMF、无设备时尝试 DSHOW。枚举不读取画面；进入页面或打开下拉列表时刷新。
- 选择保存 index/backend/device_path，重启监控生效；不打断当前监控。启动或自愈重开时按设备标识重新解析索引，所选设备拔出时明确报错，不误开另一设备。旧配置继续兼容。
- 同名设备以编号后缀区分。无设备或枚举失败时显示“无”，不覆盖原配置；枚举异常记录日志。
- 新增 tests/test_camera_selection.py：名称/无注释、无设备、插拔重排、同名设备、枚举异常、后端索引对应、缺失设备不打开其他摄像头。同步 CLI 与量化验收采集入口；补充 PyInstaller 枚举库和 DLL 收集 hook。
- 原理参考：https://github.com/lukehugh/cv2_enumerate_cameras 。当前 gesture 环境已安装该依赖。修改前存档 v1.13-pre-camera-names-20261019，原项目未同步。

- 摄像头名称版验证：定向13项通过，全量474 passed（253.95s），diff检查通过；已检查亮／暗实际Qt渲染，打包hook验证包含Windows枚举模块及其DLL。未进行完整程序打包与真实设备画面切换测试，等待人工验收。


## 2026-10-21 B1练习：三段节奏与识别窗口（用户指定方案）

- 摄像头名称选择已获用户人工验证通过。用户认可现有练习任务突出方式与页面风格，不开展整体重排；本轮替代之前的“操作说明浮层”建议。
- 开始练习区右侧加入主题三色（container/primary/card）的准备→开始→结束指引，默认2/4/2秒、匀速循环；停止练习回到最左侧。累计统计移至控制卡下方，手势列表原样保留。
- 开始练习自动开监控，首帧到达后才开始准备计时；结束练习保留监控。停止监控／启动失败会停止练习并复位。
- 准备与结束阶段不喂给手势检测器，不接收练习计数；新识别窗口重置保持计时、沿、轨迹、点击状态，保留模型和录制器，不重载模型。窗口外释放落笔／拖动状态，双手入口同样受控。
- 专用练习信号附带采集时间；工作线程和页面双重检查窗口，拒绝准备阶段、上一轮和停止后的延迟结果。
- 每轮最多记录一次结果：识别到目标即记成功并锁定，收手不再记失败；有其他动作且未成功时在窗口结束记一次失败；无结果记一次其他。成功5轮仍自动推进，目标切换从准备重新开始。
- 保留三色计数，普通运行反馈不再直接增加“其他”，避免一次操作的提示反复计数。判定仍是候选识别结果，不冒充PPT实际执行确认。
- 新增 tests/test_practice_window.py，更新现有练习测试；覆盖收手误判、准备/结束隔离、重复结果、跨轮旧信号、自动开摄像头与首帧等待、停止复位、检测器重置与双手门控。
- 修改前存档 v1.14-pre-practice-window-20261020。原项目未同步，真实摄像头练习及进度条流畅度等待人工验收；时长是首版默认值，可根据实测调整。

- 本轮最终验证：新增窗口回归7项通过；已有练习与主窗口定向33项通过；修正首帧通知与预览绘制的耦合后，全量481 passed（254.51s），git diff --check通过。已检查Windows Qt亮／暗、导航展开／收起、三阶段截图；真实摄像头识别与动画观感待人工验收。


## 2026-10-21 练习条布局与时长反馈

- 进度条缩至原可用宽度约一半，右侧垂直居中；阶段提示放在按钮与进度条之间。控制卡保持原有高度。
- 准备／开始／结束文字放入各自色块，使用注释灰色 #888888，与提示字号一致。文字在滑块之后绘制，经过标签时不遮住整字。
- 时长改为1.5／3／1.5秒（总计6秒），画面指引、工作线程识别窗口与页面计数统一使用同一时长配置。
- 新增精确边界与两种页面宽度下的布局回归；更新旧的8秒周期测试。原有成功后锁定、自动开监控、停止复位行为保留。
- 修改前存档 v1.15-pre-practice-bar-layout-20261021；原项目未同步。

- 本轮最终验证：定向43项通过；全量484 passed（266.75s），git diff --check通过。已检查亮／暗主题及导航展开／收起的实际Qt布局截图；1.5／3／1.5秒实机节奏与最终观感等待人工验收。


## 2026-10-21 结束练习停监控与控制卡布局

- 用户最新要求：点击“结束练习”同时停止监控。先关闭练习窗口并复位滑块，再调用主窗口停止监控，释放摄像头、复位预览按钮和画面，避免回调递归。累计记录保留；“练习清零”仍只结束练习和清零，不附加停止监控。
- 控制卡高度跟随第一张手势卡的实际布局高度，避免样式应用前后估算差异；阶段提示在按钮与进度条之间水平／垂直居中。
- 删除进度条内的准备／开始／结束文字，保留三色、滑块以及1.5／3／1.5秒节奏；当前阶段由中间提示表达。
- 补充主窗口结束按钮实际停止worker、按钮/预览复位、停止回调只调用一次、累计结果保留和控制卡等高回归。
- 修改前存档 v1.16-pre-practice-stop-layout-20261021；原项目未同步。

- 本轮最终验证：修正样式应用后的等高差异后，练习窗口专项11项通过；全量486 passed（267.15s），git diff --check通过。已检查亮／暗、导航展开／收起的Qt实窗布局；摄像头实际停止与再次启动等待人工验收。

## 2026-10-21 首张手势卡选中与悬停抖动

- 复现：点击首张卡片后移出鼠标，控制卡高度从54变为56，卡片内部内容也移动。选中状态的额外QSS边框改变布局尺寸，首行与控制卡的等高联动进一步传递了变化。
- 移除练习卡重复的QSS边框，统一使用CardWidget原有自绘描边。选中主题色、悬停反馈及控制卡等高行为保留，描边不再参与布局计算。
- 新增点击首卡并反复移入／移出的几何回归测试；修改前失败，修改后通过。主题测试改为验证实际绘制的描边颜色。
- 修改前存档：v1.17-pre-practice-hover-fix-20261021。练习及主窗口定向44项通过，Windows原生Qt平台的鼠标回归与描边验证2项通过。原项目未同步，实际悬停观感等待人工验收。

- 本轮最终验证：全量487 passed（163.90s），Windows原生Qt专项2项通过，git diff --check通过。待人工确认首张卡片点击后的悬停观感。

## 2026-10-21 B1.6 彩排统计摘要版（待用户审美验收）

- 用户确认练习卡悬停修复验证完毕；明确B1.4自定义手势、B1.5语音保持现状，本轮不修改这两页，直接实施B1.6。
- 保留彩排控制、彩排报告、累计统计三个模块。报告以时长、指令分发、自定义手势被拒三列摘要展示；明细使用指令次数和每页停留表格，保留完整导出与清除功能。
- 累计统计采用同样的摘要与明细样式，明确仅统计已结束彩排，重启监控后重新计数。未获取页码与无指令记录分别显示，零次与未开始不混淆。不添加综合分数或外部执行成功率。
- 明细180ms展开高度后100ms淡入，收起时先淡出；连续反向从当前状态继续。长列表内部可滚动，页面外层滚动保留；未改动全局动画。
- 开始新彩排清除旧报告及导出状态；监控中断时复位彩排按钮并明确本次未生成报告。未新增中断报告恢复或持久化统计功能。
- 修改前存档v1.18-pre-rehearsal-summary-20261021（72a4422）。仅独立副本修改，原项目未同步。用户如不满意，可回退本批提交。
- 定向11项通过，覆盖摘要/明细、导出内容、清除、空态、长列表、动画反向/清除、监控中断。已检查Windows Qt亮暗、导航展开/收起截图；截图数据仅用于布局演示，不写入真实报告或样本。

- 联合验证发现旧的删除手势测试遗留Qt延迟事件，会在后续事件循环中触发原生崩溃。补齐该测试页面及彩排测试页面的销毁清理后，原可复现的前后组合20项通过；未修改自定义手势功能代码。Windows原生Qt彩排专项11项通过。

- 最终全量490 passed（148.13s），git diff --check通过。保持本批待用户审美与真实彩排验收，未继续B1.7—8。

## 2026-10-22 B1.6 历史保存与中断恢复（待人工验收）

- 用户批准补齐彩排记录功能；起止日期、状态、原因按要求放在第三个模块之后，仍使用灰色注释样式。
- 每条记录以独立JSON原子保存到logs/rehearsals/，保留原始名称、中文动作、绑定操作、相对时间、分发结果、页码停留及读取中断次数。每秒保存进行中的记录；异常退出后只恢复到最后保存时刻，不补造丢失时段。旧版未保存的报告无法追溯恢复。
- 正常结束自动保存；停止监控、识别异常、正常退出分别保存中断原因。重复结束不重复累计，结束后时长冻结；录制器使用锁保护GUI/工作线程并发读写。保存失败保留内存数据并重试，阻止新彩排覆盖未保存结果。
- 报告标题区增加历史选择、清空显示、删除记录。清空显示不删除数据；删除记录有二次确认。启动默认显示最近的记录。坏文件保留并记日志，不影响其他有效记录读取。
- 累计从已保存的完整彩排计算，中断记录只单独查看；重启监控或程序后保留。清除累计以历史ID作为界限，不删除报告；进行中的彩排在结束后仍可加入新累计。提供当前报告与累计导出，导出包含真实起止时间与单独的导出时间。
- 明细使用中文名称，原始标识放悬停提示及导出；增加可展开操作记录。页码丢失时不继续计入上一页，同一页重复进入合计。分发结果标注执行未确认，独立识别评估仍属阶段D，未新增虚构成功率。
- 保留三模块和柔和主题。明细/操作记录先展开后淡入；淡入完成禁用透明效果缓存，修复滚动时表格空白；反向动画和多数据滚动有回归检查。亮暗、导航双态均检查1165×720实窗截图，示例数据保存在临时目录，未写入用户历史。
- 新增tests/test_rehearsal_history.py，覆盖保存重开、结束时间冻结、崩溃恢复、读取缺口、累计清除/删除、原子写失败重试、并发记录、主窗口停止监控归档、底部时间位置及动画终态。
- 修改前存档v1.19-pre-rehearsal-history-20261022（9088967）。原项目未同步。旧的“重启监控后累计清零”和“停止监控不生成报告”说明由本条覆盖。

- 最终验证：全量498 passed（161.64s），Windows原生Qt专项19项通过，git diff --check通过。已验证亮暗/导航双态/展开后滚动实窗布局；真实PPT及摄像头行为等待用户验收。

## 2026-10-22 彩排明细开合边缘抖动修复

- 用户实测反馈：查看/收起明细时模块边缘抖动。本轮修改前存档v1.20-pre-rehearsal-animation-20261022（7fe9655）。
- 修复前回归复现：明细和操作记录在动画尚为0高度时，卡片先增加12px；原因是显示/隐藏子模块导致QVBoxLayout立即添加/移除间距。
- 改用固定内容高度的裁剪容器，将12px上间距纳入同一个高度动画。父布局不再随show/hide额外插入间距；保留先展开后淡入、先淡出后收起、连续反向和淡入完成禁用透明缓存的行为。
- 附带修复：切换计数/页码相同但自定义手势绑定不同的历史报告时，缓存原先未比较标签映射，可能显示上一份绑定；现已纳入比较并加入失败场景回归。
- tests/test_rehearsal_animation.py覆盖明细/操作记录零高度开关不跳、分阶段逐帧几何跟随、历史绑定刷新；原有反向、滚动、清空、保存/恢复/导出测试继续保留。
- Windows原生Qt专项24项通过；检查范围为本次彩排页面及相关记录链路，不宣称整个项目不存在其他问题。原项目未同步，实际动画观感等待用户验收。

- 最终验证：全量503 passed（157.97s），Windows原生Qt专项24项通过，git diff --check通过；亮暗/导航双态/展开后滚动截图检查通过。待用户确认动画实际观感。

## 2026-10-22 累计统计卡片底边与注释抖动补修

- 上轮回归覆盖报告区，遗漏累计统计卡片特有的210px最小高度。实测复现：展开初段先消耗卡片留白，底边不动而注释重新分配位置，达到阈值后才开始撑高。
- 本轮将累计卡片最小高度设为收起态210px加当前展开高度，保留固定留白，注释不再被挤动。关闭、反向及刷新为空态同步恢复高度。
- 新增两种页面宽度下展开/收起逐帧回归，同时检查卡片高度、内部注释、底部时间说明间距和中途清空后的高度复位；修改前用例失败，修复后通过。
- 存档v1.21-pre-stats-animation-20261022（96df407）；原项目未同步。Windows原生Qt专项26项通过，待用户确认实际观感。

- 实时采样还复现了下方时间说明延迟一帧更新：卡片已变高而灰字尚未移动。本轮同步完成动画所在的祖先布局和滚动内容高度；新增5ms实时采样回归，验证底边单向移动、内部注释不漂移、外部灰字间距恒定。Windows原生专项最终27项通过。

- 最终验证：全量506 passed（157.21s），Windows原生Qt专项27项通过，git diff --check通过。额外实窗采样验证了报告已展开且页面滚动到底部时，累计卡片开合的屏幕底边不回弹。待用户复验。

## 2026-10-23 D最新反馈：页内验证替代弹窗

- 以本条为准：④验证手势内直接排选择行和结果表，右侧分别放灰色阶段提示与汇总；顶行按钮是开始/结束验证和清空结果。移除validation_dialog.py，改为validation_panel.py；没有独立预览、进度条、报告弹窗或自动加载历史报告。
- 1.5秒准备、3秒识别、1.5秒结束；使用已有状态悬浮窗看摄像头。结果列为逐次判定，非正确率。清空仅清显示，evaluations/已保存报告保留。
- 非模态场景补充互斥：验证中禁止录制/训练，空格不触发录制；切换离开页面、停止监控时结束并保存已完成轮次。验证自行开启的摄像头随结束关闭，原已开启监控保留，验证结束后恢复手势控制。回退点backup/d-inline-validation-20261023；当前待用户人工验收。

## 2026-10-23 D验证最新布局及准确率口径

- 去掉测试者输入框，报告参与者记为“未记录”。目标行右侧并排显示阶段和汇总。下行四列：次数、实际识别、结果、准确率，等宽居中。
- 准确率为截至当前行的累计正确/有效次数；无关动作按未误接收/有效次数；未检测到手不计入分母，零有效显示—。每行悬停解释统计口径。原逐次结果仍保留。
- 当前独立副本没有样本或模型，目标框只有无关动作；已有样本/模型类别会自动进入列表。未同步原项目、未变更训练数据。存档backup/d-validation-accuracy-20261023，等待人工验收。

## 2026-10-23 D验证模块动态高度

- 最新布局：结果表不再固定132px，也不单独滚动；空态仅保留表头，有数据后按行数增高，长列表通过页面滚动查看。④模块不吸收外层剩余高度；清空及重新开始验证时恢复紧凑空态。
- 回退点backup/d-validation-height-20261023。0/1/3/10/30行失败场景已加入回归，原生Qt专项27项通过；真实使用观感待用户验收。未修改计分、主题、训练数据或摄像头逻辑。

## 2026-10-23 E首批：收笔同帧冲突

- 用户只要求修审查第2项，明确第1/3项暂不处理；不据原建议自动实施全部优化。
- pipeline.process保存处理前的作画状态，与处理后的状态共同决定本帧冲突屏蔽。收笔清空轨迹不会在该帧放开缩放/挥手候选；无新增冷却，无GUI/摄像头/阈值调整。
- 回退点backup/e-stroke-end-20261023。新增16个边界回归，修前均复现，修后及原自定义手势专项45项通过。等待真实PPT操作验收；原项目未同步，用户配置不提交。
