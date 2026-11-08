# Oxford 3000 雅思语义试点

在本机浏览器打开仓库根目录下的 `_exports/Oxford3000_雅思语义试点/雅思语义试点.html`。音频和样题 PDF 使用同目录里的 `audio/` 和 `来源/`。这是独立的本地试点入口，适合先在电脑浏览器核对和听读。

页面从 **词头 → 词性 → 义项 → 搭配 → 完整原句** 展开。每个词头对应一张主卡。义项在词性内按频次降序，词性组按组内最高义项频次排列。默认打开首个义项，其余可展开。电脑鼠标移到卡片上显示中文，触屏用“显示中文”。每条搭配可展开出现记录，例句链接打开样题 PDF 的对应页。

试点音轨按页面词序播放。上一词、下一词和重听在本词读完后暂停，点击音频栏播放按钮或移动进度条可以继续连续播放。原序词条链接保留各词性的原发音入口，试点进度单独保存。

## 语料与口径

试点从已核对的命中中选取 30 个词，优先覆盖多词性、多义项、词形归并和固定短语。

- **雅思语料**采用 IELTS 官网 8 段听力样题稿和 3 篇学术阅读样题节选，共 219 个句段、3,377 个英文词元。只统计正文或实际对话，排除标题、任务说明、题干、答案和选项。出处登记含材料编号、PDF 页码、正文段号、句号及提取文本行号。样题署名为 © IELTS Partners，仅在本机用于个人非商业学习。[官网样题目录](https://ielts.org/take-a-test/preparation-resources/sample-test-questions/academic-test) · [版权说明](https://ielts.org/legal/ielts-copyright-and-trade-mark-statement)
- **词表与词典**以项目内 Oxford 3000 词表校验词头和链接原序发音。词性、义项以 Princeton WordNet 3.0 的 sense key 为参考，结合上下文逐条判定，中文释义由本项目整理。固定短语保留对应词典义项。试点按本批样题中的证据纳入义项，未观察到的 Oxford 词性单独标注。[WordNet 许可](https://wordnet.princeton.edu/license-and-commercial-use) · [保留的完整许可](../../../99_维护工具/Oxford3000/semantic_pilot/WORDNET-LICENSE.txt)
- **义项频次**按人工核对的命中计数，归并常见屈折变化。公司名和另一个独立词目的命中保留核对记录，固定短语中的重复词头只计一次。本次 148 处候选中，144 处计入、4 处排除。将来遇到语境不足的命中可标为待核实并从频次中排除。
- **搭配频次**只覆盖本轮已标注的原文连续词块，合并大小写及目标词的屈折变化。单个用法可以支持多个搭配。每个义项从首位搭配的记录选取一条完整原句，并高亮原文词块。同频搭配按归并后的写法排序，再以较短的完整原句优先。133 个搭配中有 9 个在各自义项内重复出现，其余是单次观察。

频次与义项先后只代表这 11 份样题正文。选词与划义都经过人工整理，样题规模及标注口径限制了频次的外推。

## 如何核对

| 项目 | 位置 |
|---|---|
| 样题来源、页码、取样范围和文件 SHA-256 | [sources.json](../../../99_维护工具/Oxford3000/semantic_pilot/sources.json) |
| 词形、WordNet 义项与中文释义 | [lexicon.json](../../../99_维护工具/Oxford3000/semantic_pilot/lexicon.json) |
| 每个命中的义项、词元序号和搭配范围 | [reviews.tsv](../../../99_维护工具/Oxford3000/semantic_pilot/reviews.tsv) |
| 30 张卡、义项与搭配次数、原句及逐处定位 | 本地试点目录中的 `统计与出处.json` |
| 数据、音轨和交互校验 | 本地试点目录中的 `验证记录.md` |

例如 `level` 的“层级”在本批语料中有 4 处，“水平或程度”有 3 处。展开首位搭配可核对同一份听力稿第 1 页的两处命中。

## 重建与扩充

构建需要 Python 3.11+、Poppler 的 `pdftotext` 和带 `libmp3lame` 的 FFmpeg。按来源登记把本人可合法使用的原 PDF 以登记文件名存到试点目录的 `来源/`。把 WordNet 3.0 压缩包放到试点目录的 `_cache/`，也可通过 `--wordnet` 指定压缩包。[维护工具](../../../99_维护工具/Oxford3000/semantic_pilot/) · [Princeton WordNet 3.0 压缩包](https://wordnetcode.princeton.edu/3.0/WordNet-3.0.tar.bz2)

```bash
python3 '99_维护工具/Oxford3000/semantic_pilot/build.py'
python3 '99_维护工具/Oxford3000/semantic_pilot/verify.py'
node '99_维护工具/Oxford3000/semantic_pilot/verify_browser.cjs'
```

Poppler 或 FFmpeg 位于非默认路径时，前两条命令可传 `--pdftotext` 和 `--ffmpeg`。浏览器检查需要可解析的 Playwright 和 Chrome，可用 `CHROME_PATH` 指定 Chrome 路径。

新增材料时先核对权利与版次，在清单登记来源和正文区域，再运行 `build.py --review` 在本机输出候选语境。每条命中应归类、明确排除或标待核实。构建校对来源文件和句段索引指纹，拒绝错位或缺少标注的候选。聚合层保留逐处证据，播放器读取生成的 `manifest`、`cards`、`evidence` 和 `stats`，无需在界面里维护词义和次数。当前 30 词上限是试点构建约束。

样题 PDF、原句、统计产物和试点成品保存在 Git 忽略的 `_exports/` 中。原序词条、原音轨和统一听读数据按各自已有方式管理。
