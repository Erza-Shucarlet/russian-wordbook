# 小陈陈的俄语单词本 📖

一个 Web 端俄语学习工具，支持生词/句式录入、数据库查询、CATTI 级学习模式，以及基于加权随机算法的选择题复习模式。

## 功能

- **📝 统一录入** — 输入俄语单词或句子，自动识别并处理（翻译/纠错）
- **📚 单词库 / 句式库** — 搜索、浏览已录入的所有内容，支持删除、合并去重、一键例句
- **📖 学习模式** — CATTI 2-3 级三选一选择题，答对答错均自动录入，支持单词/句式切换
  - 首屏先生成少量题目，第一题更快显示
  - 后台自动补充题目池，切题不再频繁等待
  - 题目生成等待态带动态加载效果
- **🎯 复习模式** — 三选一选择题，支持俄→中、中→俄、句式翻译三种题型
  - 加权随机出题，优先考察常错的单词和句式
  - 数据不足三选一时不会生成伪题
  - 每轮 10 题，答题正确/错误次数被记录
  - 句式干扰项由 AI 生成并缓存
- **🐛 反馈按钮** — 一键导出日志发送开发者
- **🎨 清爽界面** — 重新设计的顶部栏、分段导航、卡片列表和答题界面
- **⏱ 自动退出** — 浏览器关闭后一段时间自动退出本地服务，减少手动结束进程的麻烦

## 快速开始

### 使用（无需配置环境）

1. 从 [Releases](../../releases) 页面下载最新版本 zip（如 `RussianWordbook_v1.09.zip`）
2. 解压得到 `小陈陈的俄语单词本.app`
3. 双击打开
4. 浏览器自动打开 `http://127.0.0.1:8910`
5. 开始使用

> 首次启动自动在 `~/.russian-wordbook/` 创建数据库，数据持久保存。关闭浏览器后，本地服务会在心跳超时后自动退出。

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
# 输出: dist/小陈陈的俄语单词本.app (~27MB)
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

## 开发检查

```bash
venv/bin/python -m py_compile app.py db.py deepseek_client.py review_engine.py logger.py build.py
node --check static/script.js
```

## License

MIT
