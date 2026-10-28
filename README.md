# English Learning

英语学习资料、词类整理与高频通用词清单。

## 主要文件

| 文件 | 内容 |
| --- | --- |
| [英语封闭词类总览.md](英语封闭词类总览.md) | 助动词、代词、限定词、连词、介词和小品词分类 |
| [高频通用词补充.md](高频通用词补充.md) | 180 个通用动词、副词、描述词及抽象名词，附义项和句式 |
| [词汇数量统计.md](词汇数量统计.md) | 两份词表的数量、去重规则和原表拼写项索引 |
| [英语封闭词类总览.txt](英语封闭词类总览.txt) | 原始词类资料 |
| [时态.txt](时态.txt) | 时态学习笔记 |
| [smallHabits.md](smallHabits.md) | 阅读学习资料 |
| [habitsCopy.txt](habitsCopy.txt) | 阅读学习资料副本 |
| [American_Oxford_3000.pdf](American_Oxford_3000.pdf) | 美式 Oxford 3000 词表 |
| [oxford-3000-by-cefr-level.pdf](oxford-3000-by-cefr-level.pdf) | 按 CEFR 等级整理的 Oxford 3000 词表 |
| [Oxford 3000 原序学习包](Oxford3000_学习包/README.md) | 3,306 条中文释义、搭配和双语例句；2 小时 3 分钟真人连续音频及可搜索播放器 |
| [Oxford Phrase List 原序学习包](OxfordPhraseList_学习包/README.md) | 750 条短语、1,500 组双语搭配及 750 个双语例句；38 分 56 秒连续听读，真人优先、AI 补音 |

## 保存学习进度

在本文件夹中执行：

```powershell
git status
git add .
git commit -m "Update English learning notes"
```

提交前查看改动：

```powershell
git diff
```

## 两台电脑接续

首次在另一台电脑使用时，可以复制包含隐藏 `.git` 目录的整个文件夹，保留本地提交历史。

长期在两台电脑间同步时，配置远程仓库，在另一台电脑首次克隆；以后每次开始前先拉取，完成提交后推送：

```powershell
git pull --ff-only
git push
```

拉取和推送需要预先配置远程仓库及对应分支的上游。可用 `git remote -v` 查看当前远程地址。

本仓库跟踪 Markdown、TXT 和 PDF 资料；忽略系统元数据、临时文件、编辑器备份及本地环境设置。Markdown 和 TXT 在 Git 中统一使用 LF 换行。
