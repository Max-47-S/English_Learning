# Oxford 5000 补充词表

[打开听读网站的 Oxford 5000 页](https://ielts-listening-nov-2026-wx.nimble-goby-1176.chatgpt.site/study/?collection=oxford5000)。这里收录 Oxford 5000 PDF 中的 B2、C1 补充记录；Oxford 3000 基础词仍在原来的独立页，合起来覆盖 Oxford 5000 的范围。

PDF 共转录 2,012 条词性／级别记录，其中 B2 为 699 条、C1 为 1,313 条。同一词头在不同词性或级别下的记录按原表保留。牛津官方将这部分称为在 Oxford 3000 之外新增的约 2,000 个词。

| 内容 | 文件 |
|---|---|
| 按 B2、C1 和 PDF 顺序整理的词表，含中文参考释义、参考音标和原 PDF 页码 | [Oxford5000_新增词表.md](Oxford5000_新增词表.md) |
| 网页和本地学习包使用的结构化数据 | [vocabulary.json](data/vocabulary.json) |
| PDF 页数、词数、来源和校验值 | [pdf_metadata.json](data/pdf_metadata.json) |
| 词表来源与许可说明 | [来源与许可](来源与许可.md) |

网站支持搜索、按 CEFR 级别筛选、连续系统朗读、收藏和本机浏览器进度保存。Oxford 5000 PDF 未提供配套连续音频，网站使用设备系统语音；不同手机或电脑可用的声音会有所不同。中文释义和参考音标并非 Oxford 官方内容。

## 重新生成

安装 `pypdf`，下载 [官方 Oxford 5000 by CEFR PDF](../../06_原始资料/Oxford词表/oxford-5000-by-cefr-level.pdf)，并从固定的 ECDICT 提交获取 `ecdict.csv`。然后从仓库根目录运行：

```powershell
python "99_维护工具/Oxford5000/prepare_materials.py" --ecdict "C:\path\to\ecdict.csv"
python "99_维护工具/雅思听力/build_study_pack.py"
```

构建脚本核对 PDF 条数、CEFR 分组与音标／释义来源后，生成统一学习页和本地 HTML。
