# 雅思听力资料维护

学习资料位于 `05_听力与歌曲/雅思王听力语料库/`。

- `download_materials.py`：按已从官方页面核实的清单下载文件，核对 HTTP 长度、MP3 时长、PDF 页数和 SHA-256；有效文件再次运行时复用。
- `build_reference_texts.py`：读取指定 Git blob 中的静态 JSON 词表，导出 Chapter 3、4、5 的 Markdown 和 TXT 参考文本；不执行第三方 HTML 中的程序。
- `ocr_chapter11.py`、`ocr_chapter11_columns.py`：将无可用正文文本层的 Chapter 11 PDF 渲染后，通过 macOS Vision 在本机 OCR；分列识别双栏短语。
- `convert_chapter11.py`：按页面位置、章节与基线重组 OCR，应用 `chapter11_manual_corrections.json`，保留 PDF 页码与音标来源。
- `build_study_pack.py`：生成 Chapter 11 Markdown / TXT、四章学习卡、统一数据与内嵌式 HTML，并准备私人 Sites 网页的静态文件和音频代理。
- `web/`：网页源模板、样式、交互程序、音频代理源代码与 Sites 项目标识。依赖、OCR 图片和部署工作目录均放入忽略的 `_cache/`。
- `mobile_oxford.py`：接入现有 Oxford 3000 与 750 短语数据、原音轨时间轴和许可署名。音频链接固定到已核对的 Git 提交，逐词标注真人与 AI 来源，不修改原学习包。
- `web/timeline-core.js` 与 `test_mobile_timeline.cjs`：逐词时间查找、单词结束点和 4,056 条已有人声／配音时间轴的边界核验。

根据书页照片作出的校订保存在资料目录的 `data/manual_text_corrections.json`。重新生成时会先验证原始词数和起始位置，再应用校订。

在仓库根目录执行：

```sh
python -m pip install --target "99_维护工具/雅思听力/_cache/python" -r "99_维护工具/雅思听力/requirements.txt"
python "99_维护工具/雅思听力/download_materials.py"
python "99_维护工具/雅思听力/build_reference_texts.py"
python "99_维护工具/雅思听力/convert_chapter11.py"
python "99_维护工具/雅思听力/build_study_pack.py"
```

下载清单为学习资料目录中的 `data/official_downloads.json`；完整性记录为 `data/download_validation.json`；第三方文本来源与校验值为 `data/reference_text_sources.json`。原始网页、工具依赖与检索用 PDF 保存在被忽略的 `_cache/`。

OCR 需 macOS、Poppler 与 `pyobjc-framework-Vision`。现成的 OCR JSON 已放在学习包 `data/`，仅重新生成文本或网页时不必重新 OCR。网页构建默认使用 `_cache/mobile-listening-site`，也可通过 `--site-dir` 指向已有 Vinext Sites 项目；`web/site.json` 的项目 ID 须保持一致，不要重复创建 Site。

原官网音频由固定的 59 条 ID 白名单代理，支持 Range 流式传输，不接受任意 URL。官网音频使用 HTTP 原始地址，不绕过 HTTPS 证书校验。59 个 MP3 不作为网页静态资产重复上传；手机可按需保存或导入到 IndexedDB。

统一手机版新增 Oxford 两条音轨，白名单共 61 条。Oxford 源文件固定到 `3a5c95b9647b24abdcfa72eed1c423718b7b4adb` 的公开仓库文件，经过同源代理支持 Range 播放；已核对远程与本地 Git blob 一致。页面直接使用原来的 `start / spoken_end / end`，不根据单词数量平均估计时间。更新使用原 Sites 项目与 URL，维持私人访问；无需推送 English_Learning 学习仓库即可更新 Sites。
