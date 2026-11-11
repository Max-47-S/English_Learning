# 48 音标 · 真人听读

[打开 48 音标页](https://ielts-listening-nov-2026-wx.nimble-goby-1176.chatgpt.site/study/?collection=ipa) · [下载连续音轨 MP3](audio/ipa-48-follow-along.mp3)

这套卡片按常见的 48 项教学表编排，包含传统英式的 12 个单元音、8 个双元音、24 个辅音，再加 /tr/、/dr/、/ts/、/dz/ 四个辅音组合。每张卡标出两个例词中对应的拼写，也提醒 /eə/ 等在现代英音里可能出现的读法。[查理大学语音学系英音转写表](https://fonetika.ff.cuni.cz/o-fonetice/foneticka-transkripce/ipa-transcription-english/) · [华东理工大学出版社 48 项教学表](https://www.ecustpress.cn/i/files/read/562849094.pdf)

- **试听**。点“听音标”或例词，只播放所点的真人片段。部分辅音的示范带短元音，卡片会注明要听的位置。
- **跟读本卡**。按音标、第一个例词、第二个例词的顺序，每项听示范并跟读三遍。连续跟读会按音轨自动切卡。
- **速度**。1× 的人声已降到原片段语速的 80%，保留音高。每遍示范后音标留 1.8 秒，例词留 2.25 秒。可选 0.5×–2×，停顿与录音一起变速。

## 录音与重建

音标和例词录音来自 Wikimedia Commons 的语音样本和 Lingua Libre 真人词条。每张卡的“学习包音频来源与许可”列出对应原文件、录音者及原许可。[录音清单](data/recordings.json) · [卡片](data/cards.json) · [同步时间轴](data/timeline.json)

练习音轨做过剪辑、音量调整、保留音高的减速、重复与拼接，改编音轨按 [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/) 提供。

安装 FFmpeg 后，可在仓库根目录运行以下命令重建音轨，再按现有听读站的构建流程生成网页。

```powershell
python -B -X utf8 "99_维护工具/雅思听力/build_ipa_audio.py" --ffmpeg ffmpeg
```
