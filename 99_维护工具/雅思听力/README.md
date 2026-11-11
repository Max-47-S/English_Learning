# 雅思听力资料维护

学习资料位于 `05_听力与歌曲/雅思王听力语料库/`。

- `download_materials.py`：按已从官方页面核实的清单下载文件，核对 HTTP 长度、MP3 时长、PDF 页数和 SHA-256；有效文件再次运行时复用。
- `build_reference_texts.py`：读取指定 Git blob 中的静态 JSON 词表，导出 Chapter 3、4、5 的 Markdown 和 TXT 参考文本；不执行第三方 HTML 中的程序。
- `ocr_chapter11.py`、`ocr_chapter11_columns.py`：将无可用正文文本层的 Chapter 11 PDF 渲染后，通过 macOS Vision 在本机 OCR；分列识别双栏短语。
- `convert_chapter11.py`：按页面位置、章节与基线重组 OCR，应用 `chapter11_manual_corrections.json`，保留 PDF 页码与音标来源。
- `build_study_pack.py`：生成 Chapter 11 Markdown / TXT、四章学习卡、Oxford 5000 B2/C1 词表、遇词本、统一数据与内嵌式 HTML，并准备私人 Sites 网页的静态文件和音频代理。
- `web/`：网页源模板、样式、交互程序、音频代理源代码与 Sites 项目标识。依赖、OCR 图片和部署工作目录均放入忽略的 `_cache/`。
- `mobile_oxford.py`：接入现有 Oxford 3000 与 750 短语数据、原音轨时间轴和许可署名。音频链接固定到已核对的 Git 提交，逐词标注真人与 AI 来源，不修改原学习包。
- `99_维护工具/Oxford5000/prepare_materials.py`：按 Oxford 官方 PDF 转录 B2/C1 补充词表，并用固定版本的 ECDICT 生成参考释义与音标。
- `web/timeline-core.js` 与 `test_mobile_timeline.cjs`：逐词时间查找、单词结束点和 4,056 条已有人声／配音时间轴的边界核验。
- `align_ielts_timeline.py`：59 段雅思原音的无损 MP3 索引、实际发声边界与横向／纵向词序核对；`align_original_audio.py` 保留为兼容入口。结果为 `data/original_audio_timeline.json`，覆盖 8,620 次读词与 5,569 个词条。
- `web/mp3-index.js`、`web/audio-range.ts`：导入的原 MP3 补充索引，以及服务端按 Range 拼接索引与原始声音帧；分段拉取、逐块输出，不将长音轨完整缓存在 Worker 内存。`test_audio_index.cjs` 核验字节一致性、Range 边界和截断响应。
- `export_pc_pack.py`：导出 `_exports/王陆四章PC听读/` 与 ZIP，含独立 HTML、59 段带准确索引的原音与 Chapter 11 PDF；默认原版真人录音，离线包不纳入 Git。

根据书页照片作出的校订保存在资料目录的 `data/manual_text_corrections.json`。重新生成时会先验证原始词数和起始位置，再应用校订。

在仓库根目录执行：

```sh
python -m pip install --target "99_维护工具/雅思听力/_cache/python" -r "99_维护工具/雅思听力/requirements.txt"
python "99_维护工具/雅思听力/download_materials.py"
python "99_维护工具/雅思听力/build_reference_texts.py"
python "99_维护工具/雅思听力/convert_chapter11.py"
python "99_维护工具/雅思听力/build_study_pack.py"
python "99_维护工具/雅思听力/build_study_pack.py" --export-pc
```

下载清单为学习资料目录中的 `data/official_downloads.json`；完整性记录为 `data/download_validation.json`；第三方文本来源与校验值为 `data/reference_text_sources.json`。原始网页、工具依赖与检索用 PDF 保存在被忽略的 `_cache/`。

OCR 需 macOS、Poppler 与 `pyobjc-framework-Vision`。现成的 OCR JSON 已放在学习包 `data/`，仅重新生成文本或网页时不必重新 OCR。网页构建默认使用 `_cache/mobile-listening-site`，也可通过 `--site-dir` 指向已有 Vinext Sites 项目；`web/site.json` 的项目 ID 须保持一致，不要重复创建 Site。

遇词本的词条维护在 [遇词本.json](../../01_词汇与短语/遇词本.json)。新增词条沿用现有字段，并给 `id` 一个稳定、唯一的英文标识。分组为 `encounter-word-exam`、`encounter-word-accumulation`、`encounter-phrase-exam`、`encounter-phrase-accumulation`。运行 `build_study_pack.py` 后，遇词本会进入本地 HTML 与 Sites 的学习页，沿用全局搜索、系统朗读与收藏。

音频代理使用固定的 59 条雅思 ID 白名单，支持 Range 流式传输，不接受任意 URL。官方下载地址和校验记录保留用于来源追溯；不绕过 HTTPS 证书校验。59 个 MP3 不作为网页静态资产重复上传；手机可按需保存或导入到 IndexedDB。

2026-11-02 起，雅思原音也固定至学习仓库 `560f3d2b7b475dff5657631b4f16fc60939f6b36` 的 HTTPS 原文件，并逐一核对 Git blob。下载时的官方 URL 仍留在数据中作为来源记录。代理仅增加小型 Xing/Info 索引前缀并映射源文件字节区间，59 段 MPEG 声音帧逐字节不变；不重新编码，也不改停顿。播放器 URL 带索引哈希以区分旧 HTTP 缓存，已导入的旧原始 Blob 可在本机补索引。

重新对齐需另外安装 `requirements-alignment.txt` 到忽略的 `_cache/alignment-python`，并准备 `_cache/models/whisper-base.en-mlx-4bit` 模型。`PYTHONPATH` 加入该依赖目录后运行 `align_ielts_timeline.py`，可用 `--tracks` 指定片段、`--decode-only` 只分析声音边界。PCM、索引 MP3、识别结果均可复用。横向保持原词序；纵向通过实际识别核对列序，Chapter 5 Test 9 使用逐条匹配，Test 12 为四列。Chapter 4 纵向 Test 2 的 neighbouring 拆读／连读片段共享词卡，人工校订保存在 `original_audio_alignment_corrections.json`。

原音时间轴从真实发声边界提取，非等分时长。连续原音只受媒体 `currentTime/playbackRate` 驱动，不使用系统语音的词间等待定时器。含 Oxford 在内共 61 段、12,676 条音频定位点。

Chapter 11 第四组短语依据原 PDF 第 69 页合并两处换行：`rubber-wood furniture business`、`digital marketing service providers`，并修正相邻双栏行序。`ielts_text_fixes.py` 统一用于转写、对齐和构建；旧片段 ID 通过 `entryAliases` 迁移收藏与学习进度。`waterproof footwear`、`tin baths` 内部停顿合并到各自完整词卡，原音保留。

统一手机版新增 Oxford 两条音轨，白名单共 61 条。Oxford 源文件固定到 `3a5c95b9647b24abdcfa72eed1c423718b7b4adb` 的公开仓库文件，经过同源代理支持 Range 播放；已核对远程与本地 Git blob 一致。页面直接使用原来的 `start / spoken_end / end`，不根据单词数量平均估计时间。更新使用原 Sites 项目与 URL，维持私人访问；无需推送 English_Learning 学习仓库即可更新 Sites。
