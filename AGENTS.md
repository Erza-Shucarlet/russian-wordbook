# 俄语单词本 (Russian Wordbook)

## 项目概述

一个 Web 端俄语学习工具，支持生词录入、句式录入、数据库查询、以及基于加权随机算法的选择题复习模式。

- **启动方式**: 双击 `start.command`（开发）或 `.app`（打包后）
- **技术栈**: Python Flask 后端 + 原生 HTML/CSS/JS 前端 + SQLite 数据库
- **AI 集成**: DeepSeek API 用于俄语翻译、例句生成、语法纠错

---

## 项目结构

```
russian-wordbook/
├── app.py                 # Flask 后端入口，所有 API 路由
├── db.py                  # SQLite 数据库层 (CRUD + 统计)
├── deepseek_client.py     # DeepSeek API 客户端 (翻译/例句/纠错)
├── review_engine.py       # 复习引擎 (加权随机出题)
├── build.py               # PyInstaller 打包脚本
├── start.command          # 开发模式双击启动脚本
├── requirements.txt       # Python 依赖
├── .gitignore
└── static/
    ├── index.html         # 前端 SPA (5 个 Tab 页面)
    ├── style.css          # 全局样式
    └── script.js          # 前端逻辑 (API 调用 + 交互)
```

### 模块职责

| 文件 | 职责 | 关键函数 |
|---|---|---|
| `app.py` | Flask 路由、PyInstaller 兼容、启动逻辑 | `main()`, `_get_static_dir()`, `_load_api_key()` |
| `db.py` | SQLite 操作、Schema 版本迁移、数据持久化路径 | `init_db()`, `add_word()`, `get_all_items()`, `record_answer()` |
| `deepseek_client.py` | 调用 DeepSeek Chat API | `translate_word()`, `correct_sentence()`, `set_api_key()` |
| `review_engine.py` | 加权随机选题、选项生成 | `select_question()`, `_weight()`, `_generate_options()` |
| `build.py` | PyInstaller 打包为独立 .app | — |
| `static/*` | 前端 UI，通过 XHR 调用后端 API | — |

---

## 架构

```
浏览器 (static/)
    │  fetch / XHR
    ▼
Flask (app.py)  ──  port 8910
    │
    ├── db.py  ──  SQLite
    │     ├── 开发模式: data/wordbook.db (项目目录下)
    │     └── 打包模式: ~/.russian-wordbook/data/wordbook.db
    │
    ├── deepseek_client.py  ──  DeepSeek API
    │     └── 需要用户提供 API Key (持久化到 settings.json)
    │
    └── review_engine.py
          └── 读 db.get_all_items() → 加权随机 → 返回题目
```

### 数据流

1. **录入生词**: 用户输入俄语单词 → `POST /api/words` → DeepSeek 翻译+例句 → 写入 `words` 表
2. **录入句式**: 用户输入俄语句子 → `POST /api/sentences` → DeepSeek 纠错+翻译 → 写入 `sentences` 表
3. **复习出题**: `POST /api/review/start` → `review_engine.select_question()` → 按权重随机选词/句式 → 生成三选一
4. **答题记录**: `POST /api/review/answer` → `db.record_answer()` → 更新 correct/wrong 计数 → 返回下一题

---

## API 端点

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/` | 返回 static/index.html |
| GET | `/<filename>` | 静态文件 (CSS, JS) |
| GET/POST | `/api/settings` | 读取/保存 API Key |
| POST | `/api/words` | 录入生词 |
| GET | `/api/words?search=` | 查询单词列表 |
| DELETE | `/api/words/<id>` | 删除单词 |
| POST | `/api/sentences` | 录入句式 |
| GET | `/api/sentences?search=` | 查询句式列表 |
| DELETE | `/api/sentences/<id>` | 删除句式 |
| POST | `/api/review/start` | 获取一道复习题 |
| POST | `/api/review/answer` | 提交答案 + 获取下一题 |
| GET | `/api/stats` | 获取统计 (单词/句式数量) |

---

## 数据库表结构

### words
```sql
id              INTEGER PRIMARY KEY AUTOINCREMENT
russian         TEXT NOT NULL UNIQUE   -- 俄语原词（一格形式）
russian_lower   TEXT NOT NULL          -- 小写形式，用于搜索
chinese         TEXT                   -- 中文释义
examples        TEXT (JSON数组)        -- [{"ru": "...", "zh": "..."}]
correct_count   INTEGER DEFAULT 0      -- 答对次数
wrong_count     INTEGER DEFAULT 0      -- 答错次数
created_at      TIMESTAMP
```

### sentences
```sql
id              INTEGER PRIMARY KEY AUTOINCREMENT
original        TEXT NOT NULL          -- 用户原始输入
corrected       TEXT                   -- DeepSeek 修正后
chinese         TEXT                   -- 中文翻译
examples        TEXT (JSON数组)        -- 关联句式示例
correct_count   INTEGER DEFAULT 0
wrong_count     INTEGER DEFAULT 0
created_at      TIMESTAMP
```

---

## 数据安全与版本升级

### 数据位置（双重保障）

| 模式 | 数据库路径 | 升级时数据安全 |
|---|---|---|
| **打包模式** (`.app`) | `~/.russian-wordbook/data/wordbook.db` | ✅ 数据库在用户目录，替换 `.app` 不影响数据 |
| **开发模式** | `data/wordbook.db`（项目目录下） | ⚠️ 已在 `.gitignore` 中排除，但覆盖整个项目文件夹会丢失 |

打包后的 `.app` 和用户数据完全分离。用户下载新版 `.app` 直接替换即可，数据库、API Key、复习进度全部保留。

### Schema 迁移机制

`db.py` 内置了轻量的数据库版本管理系统：

- **`meta` 表**：存储 `schema_version`（当前库版本号）
- **`_CURRENT_SCHEMA_VERSION`**：代码期望的 Schema 版本
- **`_MIGRATIONS` 字典**：`{目标版本: 迁移函数}`，按顺序执行

`init_db()` 启动时自动完成：
1. 检查 `words` 表是否存在 → 全新库则创建初始表结构
2. 读取 `meta.schema_version` → 计算需要执行的迁移
3. 按版本号顺序执行迁移函数 → 更新版本号

**旧库升级示例**：用户拿着 v1 的数据库，收到 v2 的 `.app`，`init_db()` 自动执行 `v2` 的迁移，加列、加索引，已有数据不变。

### 添加新迁移（未来版本）

当需要修改数据库结构时，按以下步骤操作：

```python
# 1. 递增版本号
_CURRENT_SCHEMA_VERSION = 2  # 原来是 1

# 2. 添加迁移函数
_MIGRATIONS = {
    2: lambda conn: conn.execute("ALTER TABLE words ADD COLUMN notes TEXT DEFAULT ''"),
    # 3: lambda conn: ...,  # 下一个版本
}
```

**迁移编写规范**：
- 迁移函数接收 `conn` 参数，可以使用 `conn.execute()` 和 `conn.executescript()`
- 只改表结构（`ALTER TABLE`、`CREATE INDEX` 等），不操作数据行
- 使用 `IF NOT EXISTS` 防御性写法，避免重复执行报错
- 每次只增不减列，保持向后兼容
- 新列必须有 `DEFAULT` 值，旧行自动填充

### 数据备份建议

用户可在升级前手动备份：
```bash
cp ~/.russian-wordbook/data/wordbook.db ~/Desktop/wordbook_backup.db
```

---

## 复习算法

### 权重公式

```
weight = (wrong_count + 1) / (correct_count + wrong_count + 2)
```

| 场景 | wrong | correct | weight | 含义 |
|---|---|---|---|---|
| 新词 | 0 | 0 | 0.50 | 中等优先级 |
| 常错 | 5 | 1 | 0.75 | 高频出现 |
| 全对 | 0 | 10 | 0.08 | 低频但不遗忘 |

### 出题类型

- **word_ru_to_zh**: 给俄语选中文
- **word_zh_to_ru**: 给中文选俄语
- **sentence_ru_to_zh**: 给俄语句子选中文翻译

题目类型在可用类型中均匀随机选择，但具体出哪个词由权重决定。

---

## 开发

### 启动

```bash
# 方式 1: 双击 start.command (macOS)
# 方式 2: 命令行
source venv/bin/activate
python app.py
# 访问 http://127.0.0.1:8910
```

### 测试

```bash
# 语法检查
python3 -m py_compile app.py db.py deepseek_client.py review_engine.py

# 数据库测试
python3 -c "
import db; db.init_db()
db.add_word('тест', '测试', [])
print(db.get_words())
db.delete_word(1)
"
```

### 修改前端

前端是单 HTML 文件 (`static/index.html`) + 原生 CSS/JS。修改后直接刷新浏览器即可，无需构建步骤。

前端 JS 中的 `api()` 是所有 API 调用的封装，参数格式为 `api(method, url, body)`。

---

## 打包发行

### 构建独立 .app

```bash
python3 build.py
# 输出: dist/俄语单词本.app (~27MB)
```

`build.py` 自动创建隔离的 `.build_venv`，在其中安装 PyInstaller 并打包。构建参数：

- `--onedir`: 生成 .app 目录结构
- `--windowed`: macOS 不显示终端窗口，后台运行
- `--add-data static:static`: 将静态文件打包进 app bundle
- `--exclude-module tkinter`: 减小体积

### PyInstaller 兼容要点

两个文件有 PyInstaller 特殊处理，修改时需注意保持：

**app.py** — 静态文件路径：
```python
def _get_static_dir():
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'static')  # 打包后的路径
    return os.path.join(os.path.dirname(__file__), 'static')  # 开发路径
```

**db.py** — 数据库路径：
```python
if getattr(sys, 'frozen', False):
    _BASE_DIR = os.path.join(os.path.expanduser('~'), '.russian-wordbook')
else:
    _BASE_DIR = os.path.dirname(__file__)
```
打包后数据库存在 `~/.russian-wordbook/data/`，确保数据跨版本持久化。

### 交付

```bash
# 压缩 .app
cd dist && zip -r 俄语单词本.zip 俄语单词本.app
```

对方解压后双击 `.app` 即可使用，无需安装 Python 或任何依赖。

---

## 代码约定

- 注释和文档使用中文
- 变量名、函数名、数据库字段使用英文
- API 返回统一用 JSON，错误时返回 `{"error": "..."}` + HTTP 状态码
- 数据库操作函数在 `db.py` 中，不直接在 `app.py` 中写 SQL
- 前端无框架依赖，纯原生 JS
- 所有文件 UTF-8 编码
