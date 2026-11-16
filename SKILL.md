---
name: audio-5platform-video-pack
description: "Turn an already-produced audio narration (mp3/wav) plus topic info into five platform-specific video versions and a per-platform publish-pack web page for 微信视频号、抖音、小红书、西瓜视频、哔哩哔哩B站. Use when the user supplies a finished voiceover audio and asks to build, adapt, or package videos and publishing materials for multiple Chinese video platforms. This skill only produces specs, checklists, videos, covers and publish-pack HTML files, and never publishes or uploads to any platform."
agent_created: true
---

# 音频转五平台视频发布包

## Overview

本技能把「一段已生成好的配音音频 + 主题信息」变换为五个平台各自可直接上传的视频成片，并为每个平台产出一份**可交互发布包网页**（标题/正文/话题/置顶评论/封面/规格核对/发布步骤/文件路径）。核心原则：**只生成、不发布**——所有上传动作留给人工，本技能只负责把物料准备到「打开网页、照步骤粘贴、点发布」的程度。

## When to Use

在以下任一情形触发：
- 用户提供了**已生成完成的音频**（mp3/wav），并要求做成多平台视频 / 分发到 5 个平台。
- 用户要求基于音频生成「微信/抖音/小红书/西瓜/B站」的视频版本与发布包。
- 用户已有口播文稿 + 音频，想要「一套素材、五平台适配」的规范化产出。

不适用：需要本机 TTS 配音（那是配音环节，本技能假定音频已就绪）；纯图文/无视频；实际代发布（本技能明确不发布）。

## Input Contract（先核对输入，缺项先问）

执行前确认以下输入齐全，缺失项在开工前一次性向用户确认，不要中途反复打断：

| 项 | 说明 | 缺省处理 |
|----|------|----------|
| 音频文件 | 已生成的配音 mp3/wav（路径） | **必需**，缺失则停止并索取 |
| 主题/标题素材 | 一句话主题、核心看点、目标受众 | 可从音频转写+主题推导 |
| 文稿/字幕 | 分段或逐句文本（用于时间轴与字幕） | 若无可自动转写（需人工校对） |
| 品牌/署名 | 作者名、栏目名、公众号/账号 | 询问用户 |
| 话题标签 | 关键词或由内容生成 | 由内容自动生成初稿，人工确认 |
| 封面风格 | 平台主题色/风格偏好 | 按平台默认风格生成 |
| 输出根目录 | 归档位置 | 默认 `<工作区>/video_pack/` |

> 关键经验：**凡是用户提供的音频（尤其 WPS 生成的），一律直接使用，不要再用本机 TTS 重录**——本机 TTS 音质明显更差。

## Workflow（六阶段）

按顺序执行，每阶段产出可校验的中间件，便于回溯。

### P0 输入核对与归档目录
1. 按 Input Contract 核对输入，确认音频时长（`ffprobe`）。
2. 建立输出目录 `video_pack/`（结构见 `references/naming-and-structure.md`）。
3. 把音频转成统一工作格式：单声道/双声道 44.1kHz WAV（`ffmpeg -i in.mp3 -ar 44100 -ac 2 assets/audio.wav`）。

### P1 音频分析与时间轴对齐
1. 若已有逐句文稿：按字数比例预测每句边界，再**吸附到真实语音停顿**（`ffmpeg silencedetect` 的静音段中点 + 20ms 能量谷）。用 `scripts/build_timeline.py`。
2. 校验：帧时长合计 = 音频总时长（误差 < 0.05s），末帧强制对齐总长。
3. 产出 `timeline.json`（段/句 start/end/dur）与各版式 `frames_*.json`。

### P2 版式适配（关键：只有两类版式）
五平台不是五套版式，而是**两类**：
- **竖屏组（9:16, 1080×1920）**：微信视频号、抖音、小红书 —— 复用同一套竖屏帧。
- **横屏组（16:9, 1920×1080）**：西瓜视频、哔哩哔哩 —— 复用同一套横屏帧。

在两类版式分别渲染字幕帧/信息图卡片；平台差异主要体现在**封面比例、文案调性、标题长度**，而非视频画面。详见 `references/platform-specs.md`。

### P3 成片渲染
1. 每句一帧 → 按累计帧数 `round(t*FPS)` 切分为若干 H.264 片段（避免逐段取整累积漂移）→ concat copy → 混入音频（AAC 192k / 44.1k）。用 `scripts/render_platforms.py`。
2. 竖屏组渲染一次即可分发到微信/抖音/小红书；横屏组渲染一次分发到西瓜/B站（如需差异化文案可微调封面）。
3. 封面单独生成：按平台比例绘制（竖屏组 3:4 或 9:16；横屏组 16:9）。

### P4 发布包生成
为**每个平台**生成一份自包含 HTML（内嵌封面 base64、可一键复制的文案、可勾选步骤）+ 一份纯文本 txt（手机端备用）。用 `scripts/make_publish_kit.py`，数据驱动（配置化平台参数）。发布包必须包含七大区块：
1. 标题（主推 + 2 备选，标注字数）
2. 正文（可复制，含话题）
3. 话题标签（单独可复制）
4. 评论区置顶文案
5. 封面预览（base64 内嵌 + 尺寸说明）
6. 规格核对表（本片实测 vs 平台要求 vs 结论）
7. 发布步骤（可勾选）+ 文件绝对路径

**复制按钮规范（务必遵守，避免按钮点击无效）**：
- **禁止**把复制文本以 JS 字符串字面量内联进 `onclick`（如 `onclick="cp(this,"文本")"`）——双引号字符串嵌进双引号属性会提前闭合，导致 JS 语法错误、按钮失效。
- 一律用 `data-copy="1"` 标记按钮；纯文本从相邻 `<code>` / `<textarea>` 的 `textContent` / `value` 读取，正文/置顶等用 `data-copy-from="body|cmt"` 指向元素 id。
- 用统一事件委托脚本：剪贴板 API 优先、`document.execCommand` 降级且**检查返回值**；成功显示「✓ 已复制」，失败显示「请手动复制」并自动选中源文本。
- 修复历史页面用 `scripts/fix_copy_buttons.py`（幂等）；验收用 `scripts/verify_copy_buttons.py`（Playwright 逐按钮校验剪贴板内容与反馈）。

### P5 规格核对与归档
1. 用 `scripts/check_specs.py` 自动读视频（尺寸/时长/体积/编码）与封面（尺寸/大小），对照 `references/platform-specs.md` 输出核对结果。
2. 生成「成果说明」（本次产出的文件清单 + 各平台对应文件 + 规格结论 + 需人工确认项）。
3. 交付：各平台发布包 HTML + 视频 + 封面 + 总清单，`present_files` 呈现。

## Human Confirmation Gates（需人工确认，不得自动越过）

以下环节**必须**交由用户确认，本技能不代替决策，更不代替发布：

1. **音频内容确认**：确认音频与主题一致、无口误/敏感内容（可在交付前提示用户自查）。
2. **文案口径确认**：标题钩子、正文卖点、话题标签的取舍由用户拍板；本技能只给主推+备选。
3. **封面选型确认**：多版封面由用户选定；上传时必须用「自定义封面」，不得用系统截帧。
4. **规格最终核对**：平台规则会变，`references/platform-specs.md` 为基准值，**上传前须以各平台官方最新要求为准**（尤其时长上限、体积上限、标题字数）。
5. **发布动作**：上传、填表、点发布全部由人工在平台完成；本技能**不登录、不上传、不发布**。
6. **合规确认**：原创声明、版权音乐、无水印、无违规词，由人工最终确认。

## Outputs & Archival

产出清单与目录结构固定化，便于归档复用，详见 `references/naming-and-structure.md`。核心输出：
- 每平台 1 个视频 mp4（竖屏组可共用，横屏组可共用）
- 每平台 1 张封面 png/jpg
- 每平台 1 个发布包 html + 1 个发布文案 txt
- 1 份总成果说明（`成果说明.md`）与 1 份规格核对结果

## Resources

- `references/platform-specs.md` —— 五平台规格核对表（尺寸/比例/时长/体积/编码/标题/正文/话题/封面），含竖屏组 vs 横屏组差异。
- `references/checklist.md` —— 发布前检查清单（视频/封面/文案/合规四类，可勾选）。
- `references/naming-and-structure.md` —— 文件命名规范、目录结构、输出文件清单、需人工确认清单。
- `scripts/build_timeline.py` —— 音频边界吸附对齐，产出 timeline + frames json。
- `scripts/render_platforms.py` —— 按帧 json 渲染竖屏/横屏成片并混音。
- `scripts/make_publish_kit.py` —— 五平台发布包 HTML + txt 生成器（配置驱动）。
- `scripts/check_specs.py` —— 用 ffprobe 读取实测规格并对照平台要求出核对结果。
- `scripts/fix_copy_buttons.py` —— 幂等修复历史发布包复制按钮（消除内联 onclick 引号嵌套，替换为 data 属性 + DOM 取值 + 统一脚本）。
- `scripts/verify_copy_buttons.py` —— Playwright 浏览器实测所有复制按钮的剪贴板内容与成功/失败反馈。
- `assets/publish_kit_template.html` —— 发布包网页版式模板（七大区块占位）。

## 禁止事项

- 不调用任何平台 API/浏览器代为登录、上传或发布。
- 不在未经用户确认时替换用户音频或改写主题口径。
- 不把「基准规格」当作「官方实时规格」对外承诺，交付时明确提示人工复核。
