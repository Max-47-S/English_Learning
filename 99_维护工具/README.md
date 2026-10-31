# 维护工具

[返回学习导航](../README.md)

生成、下载、打包和校验脚本集中保存在这里。日常学习直接打开各分类里的 Markdown 或听读网页。

以下命令均在**仓库根目录**执行；脚本根据自身位置寻找数据，在其他工作目录运行也能找到学习包。

| 目录 | 对应内容 |
| --- | --- |
| [Oxford3000/](Oxford3000/) | 词表提取、词条补充、录音准备、音频与页面生成、校验及打包 |
| [OxfordPhraseList/](OxfordPhraseList/) | 短语提取、真人录音与 AI 补音、材料和页面生成、校验及本地网页服务 |
| [日常对话/](日常对话/) | 从母句数据生成 120 句学习包 |
| [通用/](通用/) | 仓库链接检查、两个播放器的操作测试 |

## Oxford 3000

只修改播放器时：

```sh
python "99_维护工具/Oxford3000/build_player.py"
```

学习包位于 `01_词汇与短语/Oxford3000_学习包/`。人工补充数据保存在该包的 `data/`，例如 `manual_enrichment.json`、`sense_overrides.json`、`pos_overrides.json`、`qa_overrides.json` 和 `common_glosses.json`。

完整制作顺序：`prepare_sources.py extract` → `index_collections.py` → `plan_audio.py` → `download_required.py`（仍有缺失时）→ `enrich_vocab.py` → `build_audio.py` → `build_materials.py` → `build_player.py` → `validate_materials.py`。下载数据源见 `prepare_sources.py`、`download_collections.py` 及学习包的来源清单。

完整制作依赖 Python、pdfplumber、pypdf、NLTK、OpenCC、aiohttp、PyAV、NumPy、mutagen 和 imageio-ffmpeg。原始下载和本机依赖缓存在学习包的 `_cache/`，不随 Git 提交。仅生成播放器使用 Python 标准库即可。`package_download.py` 将 ZIP 输出到被忽略的 `_exports/`，保留分类后的相对目录。

## 750 短语

```sh
python "99_维护工具/OxfordPhraseList/build_player.py"
```

学习包位于 `01_词汇与短语/OxfordPhraseList_学习包/`。完整制作的依赖见 [requirements.txt](OxfordPhraseList/requirements.txt)；提取、音频、材料、网页和校验脚本都在同一维护目录。原始 PDF 集中放在 `06_原始资料/Oxford词表/`。

## 手机通过电脑访问750短语

```sh
python "99_维护工具/OxfordPhraseList/serve.py"
```

电脑浏览器打开 `http://127.0.0.1:8767/连续听读.html`。需要同一局域网的手机访问时，增加 `--host 0.0.0.0`，并把手机浏览器地址中的 `127.0.0.1` 换成电脑的局域网 IP。服务支持 MP3 Range 请求，按 Ctrl+C 结束。

## 日常对话母体

内容源位于 `03_日常对话/日常对话母体_120句/data/母句.json` 与该目录下的 `练习说明.md`。使用 Node.js 18 或以上重新生成：

```sh
node "99_维护工具/日常对话/build.mjs"
```

脚本会核对 Oxford 词汇和短语的映射，生成学习文件和 `data/覆盖核对.json`。

## 检查与浏览器测试

检查已跟踪文件中的本地链接、学习包数据与媒体路径：

```sh
python "99_维护工具/通用/check_repository.py"
```

安装 Playwright 后，使用本机 Chrome 测试两个播放器：

```sh
node "99_维护工具/通用/check_playback_controls.cjs"
```

可通过 `CHROME_PATH` 指定浏览器程序。设置 `PLAYER_TEST_BASE_URL` 为仓库根目录的本地 HTTP 地址后，还会测试音频元数据尚未载入时点击切词。测试使用真实本地 MP3；手机操作通过桌面 Chrome 模拟，未覆盖真实手机或 Safari。

原有的 750 短语全面交互检查为 `OxfordPhraseList/check_player.cjs`，可通过 `PLAYER_BASE_URL` 指定该学习包的 HTTP 地址。
