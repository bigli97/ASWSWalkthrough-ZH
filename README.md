# A Struggle With Sin 中文攻略 · 第一阶段

已从相邻的 `ASWSWalkthrough/` 提取 53 章；仅翻译 3 个样例：基本信息、技巧与窍门、序章。中文仍待人工审核。原源码保持不动。

## 日常使用

在本目录打开终端：

```sh
make preview
```

访问 http://127.0.0.1:8000 。修改 `docs/` 中的中文 Markdown 并保存，预览会自动刷新。终端按 Ctrl+C 停止。依赖已安装时，正文、图片、导航、中文搜索均不依赖外网；作者等外部链接需要联网。不以双击 HTML 作为离线使用方式。

```sh
make build
make pdf
```

网站产物：`dist/site/`。PDF：`dist/pdf/walkthrough-zh.pdf`，按原站入口顺序收入已有中文章节，包含可点击目录和书签。PDF 不收入尚未翻译的章节。

换电脑时首次执行 `make setup` 安装依赖，需要联网。当前验证环境是 macOS、Python 3.9、Pandoc；PDF 使用 Typst 和系统 PingFang SC 字体。其他操作系统的字体适配列为后续事项。

## 你只需要修改的内容

- `docs/01-info.md`：基本信息。
- `docs/02-tips.md`：技巧与窍门。
- `docs/04-intro.md`：序章；编号 04 对应原入口顺序，03 尚未翻译。
- `glossary.md`：术语表；修改后重新构建会更新搜索分词，后续翻译批次读取最新版术语。不会自动改写已有中文正文。

`<!-- source:0001 -->` 等注释用于记录原文块对应关系，不会显示在网站或 PDF 中。正常修订正文即可，建议保留这些注释。中文图片资源已放在 `docs/assets/images/`，Markdown 编辑器也可显示。

## 自动流程与保护边界

- `make extract`：识别入口顺序，提取原文、图片和链接，生成原文 Markdown、章节清单与分块请求，不翻译、不改写中文文件。
- `make pending`：列出样例范围内尚未完成的批次；已完成批次经结构校验后跳过。
- `make assemble`：将已齐全的分块中文草稿自动拼成完整章节；`docs/` 目标文件只要存在，就跳过，绝不覆盖。
- `make build` / `make preview` / `make pdf`：只读取 `docs/`，自动生成导航和暂存页面，不回写中文正文。
- `make check`：检查样例草稿结构、块顺序以及构建产物的本地图片、链接、锚点。

本阶段的翻译由当前助手完成并直接写入 `translation/drafts/`；脚本负责请求分块、校验、状态和拼接，没有配置外部模型 API，也不会在运行构建时触发翻译。后续确认扩大范围后，由助手读取 `translation/requests/` 和术语表，继续处理缺失批次；你不需要手工创建 JSON 或拼接章节。

`docs/` 是人工中文内容的唯一输入，`translation/` 是自动中间产物，`.build/` 和 `dist/` 可重新生成。请保留 `docs/` 和 `glossary.md`；不要把删除中文文件当作刷新方式。

## 验证与边界

见 `translation/验收记录.md`、`translation/acceptance.json` 和 `translation/validation.json`。本轮没有批量翻译其余 50 章；待译章节明确显示状态并提供本地英文原文入口。剩余问题列于 `TODO.md`，不影响 3 章样例验收。
