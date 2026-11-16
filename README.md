# audio-5platform-video-pack

WorkBuddy skill：把一段**已生成好的配音音频 + 主题信息**转成微信视频号 / 抖音 / 小红书 / 西瓜视频 / 哔哩哔哩五个平台的视频版本与各自的可交互发布包网页。

> 核心原则：**只生成物料，绝不代发布**。

## 能力
- 音频时间轴对齐、字幕帧渲染、竖屏(1080×1920)/横屏(1920×1080)两类成片
- 五平台封面、文案、规格核对、发布步骤、文件路径清单
- 发布包 HTML 一键复制按钮（剪贴板 API + execCommand 降级，含成功/失败反馈）

## 结构
- `SKILL.md` —— 六阶段工作流、输入契约、人工确认闸门
- `references/` —— 平台规格、检查清单、命名与目录结构
- `scripts/` —— 时间轴/渲染/发布包/规格核对/复制按钮修复与验证工具
- `assets/publish_kit_template.html` —— 发布包网页模板

## 复制按钮
发布包的一键复制统一用 `data-copy` + DOM 取值 + 事件委托，禁止把文本内联进 `onclick`（会触发引号嵌套导致按钮失效）。历史页面可用 `scripts/fix_copy_buttons.py` 幂等修复，`scripts/verify_copy_buttons.py`（需 playwright）做浏览器实测。

## 安装
将本目录放到 WorkBuddy 的用户级 skills 目录：`~/.workbuddy/skills/audio-5platform-video-pack/`。
