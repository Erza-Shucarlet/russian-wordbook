# 俄语单词本 📖

一个 Web 端俄语学习工具，支持生词录入、句式录入、数据库查询，以及基于加权随机算法的选择题复习模式。

## 功能

- **📝 生词录入** — 输入俄语单词，自动调用 DeepSeek API 获取中文翻译和例句
- **📝 句式录入** — 输入俄语句子，自动修正语法错误并给出中文翻译
- **📚 单词库 / 句式库** — 搜索、浏览已录入的所有内容，支持删除
- **🎯 复习模式** — 三选一选择题，支持俄→中、中→俄、句式翻译三种题型
  - 加权随机出题，优先考察常错的单词和句式
  - 答题正确/错误次数被记录，全对的低频出现但不遗忘

## 快速开始

### 使用（无需配置环境）

1. 下载 `俄语单词本.app`
2. 双击打开
3. 浏览器自动打开 `http://127.0.0.1:8910`
4. 开始使用

> 首次启动自动在 `~/.russian-wordbook/` 创建数据库，数据持久保存。

### 开发

```bash
# 双击 start.command
# 或命令行：
source venv/bin/activate
python app.py
```

### 打包

```bash
python3 build.py
# 输出: dist/俄语单词本.app (~27MB)
```

## 技术栈

- **后端**: Python Flask
- **数据库**: SQLite
- **前端**: 原生 HTML/CSS/JS
- **AI**: DeepSeek API（翻译、例句、语法纠错）
- **打包**: PyInstaller

## 项目结构

```
russian-wordbook/
├── app.py              # Flask 后端
├── db.py               # 数据库层（含 Schema 迁移）
├── deepseek_client.py  # DeepSeek API 客户端
├── review_engine.py    # 复习引擎（加权随机）
├── build.py            # PyInstaller 打包脚本
├── start.command       # 开发启动脚本
└── static/
    ├── index.html
    ├── style.css
    └── script.js
```

## 数据安全

- 数据库存储在 `~/.russian-wordbook/data/`，与 `.app` 完全分离
- 更新版本时替换 `.app` 不影响已有数据
- 内置 Schema 版本迁移机制，新版加字段不会破坏旧库

## License

MIT
