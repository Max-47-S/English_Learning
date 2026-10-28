# Oxford Phrase List · 连续听读学习包

750 条短语，按原 PDF 的级别与四栏阅读顺序整理。每条配有中文释义、两组中英用法搭配、原创双语例句；其中 248 条另有语法或辨析提示。

| 级别 | 条数 | 学习文件 |
| --- | ---: | --- |
| A1 | 200 | [A1 学习版](OxfordPhraseList_A1.md) |
| A2 | 175 | [A2 学习版](OxfordPhraseList_A2.md) |
| B1 | 175 | [B1 学习版](OxfordPhraseList_B1.md) |
| B2 | 125 | [B2 学习版](OxfordPhraseList_B2.md) |
| C1 | 75 | [C1 学习版](OxfordPhraseList_C1.md) |

## 开始使用

1. 打开 [连续听读网页](连续听读.html)，点击播放，从第一条连续听到最后一条。
2. 点击列表里的短语可从该条开始，支持上一条、下一条、重听、0.75–1.5 倍速、按英文或中文搜索及按级别筛选。
3. 点击“继续上次进度”恢复同一浏览器保存的位置。级别筛选只改变列表，连续音轨仍按完整 PDF 顺序播放。
4. 阅读 [完整 Markdown 学习版](OxfordPhraseList_原序学习版.md)，或上表中的分级文件；其中的时间链接可打开网页并定位。

网页与音频使用本地文件，不加载在线字体或外部脚本。解压后保留整个文件夹结构，使用支持本地音频的浏览器打开 HTML。移动端具体的本地文件打开方式取决于系统与浏览器；同一局域网也可以由电脑运行下面的本地服务器，再用手机浏览器访问。

音频也可直接用任意支持 MP3 的播放器播放：[00:38:56 完整连续音频](audio/OxfordPhraseList_连续听读.mp3)，配套 [LRC 时间标签](audio/OxfordPhraseList_连续听读.lrc)。

## 内容与音频

- A1 200、A2 175、B1 175、B2 125、C1 75，共 750 个主条目；原表附列的缩进示例未额外计数。
- 真人录音 **350 条**，AI 补音 **400 条**；AI 使用 en-GB-SoniaNeural。每条和播放器中均有明确标记，实际朗读内容列在“音频示范”中。
- 音频朗读英文短语或具体用法，条间停顿 **1.8 秒**；中文、搭配和例句供同步阅读。真人录音包含不同朗读者与口音。
- 对含 sb/sth、X 或省略号的句型，用固定短语部分或具体填充后的表达来示范，不把这些占位字母作为正常单词跟读。
- 这份表是独立的 Oxford Phrase List；750 条不等于 Oxford 3000 里多出的 306 条，不能据此直接相加计算去重词汇量。
- 词头与级别取自原表，学习释义及双语例句由本包编写；不是牛津官方音频、释义或例句产品。来源与逐段署名见 [来源与许可](来源与许可.md)。

## 本地网页服务（可选）

直接打开 HTML 即可先试用。若系统限制本地 HTML 读取旁边的音频，电脑安装 Python 后，在本学习包文件夹运行：

```powershell
python scripts/serve.py
```

电脑访问 http://127.0.0.1:8767/连续听读.html 。如要让同一局域网的手机访问：

```powershell
python scripts/serve.py --host 0.0.0.0
```

在手机浏览器中把 127.0.0.1 换成电脑的局域网 IP，并保留端口 8767。系统询问防火墙权限时，仅在你需要局域网访问的网络环境中放行。服务支持 MP3 Range 请求，可直接跳转时间点；Ctrl+C 结束服务。播放器本身不依赖 Python。

## 数据与校验

- [vocabulary.json](data/vocabulary.json)：750 条完整双语学习资料。
- [audio_timeline.json](data/audio_timeline.json)：逐条时间轴、类型、朗读文字、来源。
- [pdf_metadata.json](data/pdf_metadata.json)：原 PDF URL、SHA-256、页数及提取数量。
- [validation_report.json](data/validation_report.json)：自动校验结果；[browser_validation.json](data/browser_validation.json)：浏览器交互校验结果。
- 脚本用于重新生成资料；中间下载、合成缓存及本机依赖放在被忽略的 _cache/，成品播放不需要这些缓存。

原 PDF SHA-256：`35da430c8c0353d4a44c6293ca0d05ae00787488562beaed1ff2835c6e37e118`。
