"""
小陈陈的俄语单词本 — Flask 后端
支持 PyInstaller 打包后独立运行
"""

import os
import sys
import json
import random
import time
import webbrowser
import threading
import logger
from flask import Flask, request, jsonify, send_from_directory
import db
import deepseek_client
import review_engine


# ─── PyInstaller 资源路径 ──────────────────────────────────────

def _get_static_dir():
    """获取静态文件目录（兼容 PyInstaller 打包）"""
    if getattr(sys, 'frozen', False):
        return os.path.join(sys._MEIPASS, 'static')
    return os.path.join(os.path.dirname(__file__), 'static')

STATIC_DIR = _get_static_dir()

app = Flask(__name__)


# ─── 浏览器心跳与自动退出 ─────────────────────────────────────

_HEARTBEAT_TIMEOUT_SECONDS = 90
_HEARTBEAT_CHECK_SECONDS = 10
_last_heartbeat = 0.0
_heartbeat_monitor_started = False
_heartbeat_lock = threading.Lock()


def _heartbeat_monitor():
    """浏览器关闭后自动退出本地服务"""
    while True:
        time.sleep(_HEARTBEAT_CHECK_SECONDS)
        with _heartbeat_lock:
            last = _last_heartbeat
        if last and time.time() - last > _HEARTBEAT_TIMEOUT_SECONDS:
            logger.info("浏览器心跳超时，自动退出本地服务")
            os._exit(0)


def _touch_heartbeat():
    """记录前端心跳，并按需启动监控线程"""
    global _last_heartbeat, _heartbeat_monitor_started
    with _heartbeat_lock:
        _last_heartbeat = time.time()
        if not _heartbeat_monitor_started:
            threading.Thread(target=_heartbeat_monitor, daemon=True).start()
            _heartbeat_monitor_started = True


@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')


# 其他静态文件（CSS, JS 等）
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)


@app.route('/api/heartbeat', methods=['POST'])
def heartbeat():
    """前端页面心跳；心跳停止一段时间后服务自动退出"""
    _touch_heartbeat()
    return jsonify({"ok": True})


# ─── 设置 ─────────────────────────────────────────────────────

@app.route('/api/settings', methods=['POST'])
def save_settings():
    data = request.get_json()
    key = data.get('api_key', '').strip()
    persisted = False
    if key:
        deepseek_client.set_api_key(key)
        persisted = _save_api_key(key)
    return jsonify({
        "ok": True,
        "has_key": bool(key),
        "persisted": persisted,
    })


@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify({
        "has_key": bool(deepseek_client.get_api_key()),
        "settings_path": db.SETTINGS_PATH,
        "file_exists": os.path.exists(db.SETTINGS_PATH),
    })


# ─── API Key 持久化 ───────────────────────────────────────────

def _save_api_key(key: str) -> bool:
    """将 API Key 保存到本地文件，返回是否成功"""
    try:
        os.makedirs(os.path.dirname(db.SETTINGS_PATH), exist_ok=True)
        with open(db.SETTINGS_PATH, 'w') as f:
            json.dump({"api_key": key}, f)
        return True
    except Exception:
        return False


def _load_api_key() -> str | None:
    """从本地文件加载 API Key"""
    try:
        if os.path.exists(db.SETTINGS_PATH):
            with open(db.SETTINGS_PATH) as f:
                data = json.load(f)
                return data.get('api_key', '')
    except Exception:
        pass
    return None


# ─── 单词 API ─────────────────────────────────────────────────

@app.route('/api/entry', methods=['POST'])
def add_entry():
    """统一录入 — 自动判断单词或句式，调用 DeepSeek 翻译/纠错"""
    data = request.get_json()
    text = data.get('text', '').strip()
    if not text:
        return jsonify({"error": "请输入俄语内容"}), 400

    is_sentence = ' ' in text

    if is_sentence:
        # 句式录入
        if db.sentence_exists(text):
            logger.info(f"重复句式: {text[:50]}")
            return jsonify({"error": "该句式已存在"}), 409

        corrected = text
        chinese = ""
        examples = []
        try:
            if deepseek_client.get_api_key():
                result = deepseek_client.correct_sentence(text)
                corrected = result.get('corrected', text)
                chinese = result.get('chinese', '')
                examples = result.get('examples', [])
        except Exception:
            pass

        sent_id = db.add_sentence(text, corrected, chinese, examples)
        return jsonify({
            "ok": True,
            "type": "sentence",
            "id": sent_id,
            "original": text,
            "corrected": corrected,
            "chinese": chinese,
            "examples": examples,
            "is_corrected": corrected != text,
        })

    else:
        # 单词录入（含拼写纠错）
        corrected_russian = text
        original_russian = text
        chinese = ""
        examples = []
        try:
            if deepseek_client.get_api_key():
                result = deepseek_client.translate_word(text)
                corrected_russian = result.get('russian', text)
                chinese = result.get('chinese', '')
                examples = result.get('examples', [])
        except Exception:
            pass

        # 用正确拼写存储（如果已存在该正确拼写则拒绝）
        if db.word_exists(corrected_russian):
            return jsonify({"error": f"单词 '{corrected_russian}' 已存在"}), 409

        word_id = db.add_word(corrected_russian, chinese, examples)
        if word_id is None:
            return jsonify({"error": "单词已存在"}), 409

        return jsonify({
            "ok": True,
            "type": "word",
            "id": word_id,
            "russian": corrected_russian,
            "chinese": chinese,
            "examples": examples,
            "is_corrected": corrected_russian != original_russian,
            "original": original_russian if corrected_russian != original_russian else None,
        })


@app.route('/api/words', methods=['POST'])
def add_word():
    """录入生词 — 自动调用 DeepSeek 获取翻译和例句"""
    data = request.get_json()
    russian = data.get('russian', '').strip()
    if not russian:
        return jsonify({"error": "请输入俄语单词"}), 400
    if ' ' in russian:
        return jsonify({"error": "检测到空格，请到「录入句式」添加句子"}), 400

    # 检查是否已存在
    if db.word_exists(russian):
        return jsonify({"error": f"单词 '{russian}' 已存在"}), 409

    # 调用 DeepSeek 获取翻译和例句
    chinese = ""
    examples = []
    try:
        if deepseek_client.get_api_key():
            result = deepseek_client.translate_word(russian)
            chinese = result.get('chinese', '')
            examples = result.get('examples', [])
        else:
            chinese = data.get('chinese', '').strip()
            examples = data.get('examples', [])
    except Exception as e:
        # API 调用失败时使用用户提供的值
        chinese = data.get('chinese', '').strip()
        examples = data.get('examples', [])

    word_id = db.add_word(russian, chinese, examples)
    if word_id is None:
        return jsonify({"error": "单词已存在"}), 409

    return jsonify({
        "ok": True,
        "id": word_id,
        "russian": russian,
        "chinese": chinese,
        "examples": examples,
    })


@app.route('/api/words', methods=['GET'])
def list_words():
    search = request.args.get('search', '').strip() or None
    words = db.get_words(search=search)
    return jsonify({"words": words})


@app.route('/api/words/dedup', methods=['POST'])
def dedup_words():
    """合并重复单词：保留翻译最完整的，合并答题统计"""
    removed = db.dedup_words()
    return jsonify({"ok": True, "removed": removed})


@app.route('/api/sentences/dedup', methods=['POST'])
def dedup_sentences():
    """合并重复句式：保留翻译最完整的，合并答题统计"""
    removed = db.dedup_sentences()
    return jsonify({"ok": True, "removed": removed})


@app.route('/api/sentences/retro-correct', methods=['POST'])
def retro_correct():
    """一键纠正所有未修正的句式"""
    if not deepseek_client.get_api_key():
        return jsonify({"error": "请先设置 API Key"}), 400

    # 查找 corrected == original 的句式（未被修正过）
    import db
    conn = db.get_conn()
    rows = conn.execute(
        "SELECT * FROM sentences WHERE corrected = original OR corrected = ''"
    ).fetchall()
    conn.close()
    uncorrected = [db._row_to_dict(r) for r in rows]

    corrected_count = 0
    for s in uncorrected:
        try:
            result = deepseek_client.correct_sentence(s['original'])
            new_corrected = result.get('corrected', s['original'])
            if new_corrected != s['original']:
                db.update_sentence_correction(s['id'], new_corrected, result.get('chinese', s['chinese']), result.get('examples', s['examples']))
                corrected_count += 1
        except Exception:
            pass

    return jsonify({
        "ok": True,
        "corrected": corrected_count,
        "total": len(uncorrected),
    })


@app.route('/api/words/retro-examples', methods=['POST'])
def retro_examples():
    """为缺少例句的单词补生成例句（返回列表供前端逐条处理）"""
    words = db.get_words(limit=9999)
    no_examples = [{"id": w['id'], "russian": w['russian']} for w in words if not w.get('examples') or len(w['examples']) == 0]
    return jsonify({"ok": True, "words": no_examples})


@app.route('/api/words/retro-example/<int:word_id>', methods=['POST'])
def retro_example_one(word_id):
    """为单个单词生成例句"""
    if not deepseek_client.get_api_key():
        return jsonify({"error": "请先设置 API Key"}), 400

    try:
        words = db.get_words(limit=9999)
        word = next((w for w in words if w['id'] == word_id), None)
        if not word:
            return jsonify({"error": "单词不存在"}), 404

        result = deepseek_client.translate_word(word['russian'])
        examples = result.get('examples', [])
        if examples:
            db.update_word_examples(word_id, examples)
        return jsonify({"ok": True, "has_examples": len(examples) > 0})
    except Exception:
        return jsonify({"ok": False})


@app.route('/api/words/retro-translate', methods=['POST'])
def retro_translate():
    """补译所有缺少中文翻译的单词"""
    if not deepseek_client.get_api_key():
        return jsonify({"error": "请先设置 API Key"}), 400

    untranslated = db.get_untranslated_words()
    if not untranslated:
        return jsonify({"ok": True, "translated": 0, "message": "所有单词已有翻译"})

    translated = 0
    failures = 0
    first_error = None
    for word in untranslated:
        try:
            result = deepseek_client.translate_word(word['russian'])
            chinese = result.get('chinese', '').strip()
            examples = result.get('examples', [])
            if chinese:
                db.update_word_translation(word['id'], chinese, examples)
                translated += 1
            else:
                failures += 1
        except Exception as e:
            failures += 1
            if first_error is None:
                first_error = str(e)[:200]

    return jsonify({
        "ok": True,
        "translated": translated,
        "total": len(untranslated),
        "failures": failures,
        "first_error": first_error,
    })


@app.route('/api/words/<int:word_id>', methods=['DELETE'])
def remove_word(word_id):
    db.delete_word(word_id)
    return jsonify({"ok": True})


# ─── 句式 API ─────────────────────────────────────────────────

@app.route('/api/sentences', methods=['POST'])
def add_sentence():
    """录入句式 — 自动调用 DeepSeek 修正语法并翻译"""
    data = request.get_json()
    original = data.get('sentence', '').strip()
    if not original:
        return jsonify({"error": "请输入俄语句式"}), 400

    # 调用 DeepSeek 修正语法并翻译
    corrected = ""
    chinese = ""
    examples = []
    try:
        if deepseek_client.get_api_key():
            result = deepseek_client.correct_sentence(original)
            corrected = result.get('corrected', original)
            chinese = result.get('chinese', '')
            examples = result.get('examples', [])
        else:
            corrected = data.get('corrected', original).strip()
            chinese = data.get('chinese', '').strip()
            examples = data.get('examples', [])
    except Exception as e:
        corrected = data.get('corrected', original).strip()
        chinese = data.get('chinese', '').strip()
        examples = data.get('examples', [])

    sent_id = db.add_sentence(original, corrected, chinese, examples)
    return jsonify({
        "ok": True,
        "id": sent_id,
        "original": original,
        "corrected": corrected,
        "chinese": chinese,
        "examples": examples,
    })


@app.route('/api/sentences', methods=['GET'])
def list_sentences():
    search = request.args.get('search', '').strip() or None
    sentences = db.get_sentences(search=search)
    return jsonify({"sentences": sentences})


@app.route('/api/sentences/<int:sent_id>', methods=['DELETE'])
def remove_sentence(sent_id):
    db.delete_sentence(sent_id)
    return jsonify({"ok": True})


# ─── 复习 API ─────────────────────────────────────────────────

@app.route('/api/review/start', methods=['POST'])
def review_start():
    """开始/继续复习 — 返回一道题"""
    question = review_engine.select_question()
    if question is None:
        return jsonify({"done": True, "message": "还没有可复习的内容，请先录入单词或句式"})
    return jsonify({"done": False, "question": question})


@app.route('/api/review/answer', methods=['POST'])
def review_answer():
    """提交答案"""
    data = request.get_json()
    item_id = data.get('item_id')
    table = data.get('table')
    chosen = data.get('chosen')  # 用户选择的索引
    correct_index = data.get('correct_index')

    if table not in ('words', 'sentences'):
        return jsonify({"error": "invalid table"}), 400

    is_correct = (chosen == correct_index)
    db.record_answer(table, item_id, is_correct)

    # 自动加载下一题
    next_question = review_engine.select_question()

    return jsonify({
        "is_correct": is_correct,
        "correct_index": correct_index,
        "done": next_question is None,
        "next_question": next_question,
    })


# ─── 学习 API ─────────────────────────────────────────────────

@app.route('/api/learn/batch', methods=['POST'])
def learn_batch():
    """批量生成 10 道学习题（一次 API 调用）"""
    if not deepseek_client.get_api_key():
        return jsonify({"error": "请先设置 API Key"}), 400

    data = request.get_json() or {}
    level = data.get('level', 'catti3')
    learn_type = data.get('type', 'word')
    count = max(1, min(int(data.get('count', 10)), 10))

    try:
        if learn_type == 'word':
            existing = db.get_words(limit=500)
            existing_list = [w['russian'] for w in existing]
            questions = deepseek_client.generate_word_batch(level, existing_list, count)
        else:
            existing = db.get_sentences(limit=500)
            existing_list = [s['corrected'] or s['original'] for s in existing]
            questions = deepseek_client.generate_sentence_batch(level, existing_list, count)

        # 添加 type 字段
        # 安全网：后端始终打乱选项顺序，避免 AI 把正确答案放在固定位置
        for q in questions:
            q['type'] = learn_type
            opts = q.get('options', [])
            if len(opts) >= 3:
                correct_idx = q.get('correct_index', 0)
                correct_val = opts[correct_idx] if correct_idx < len(opts) else opts[0]
                random.shuffle(opts)
                q['correct_index'] = opts.index(correct_val)
                q['options'] = opts

        logger.info(f"学习批量生成完成: {len(questions)} 题")
        return jsonify({"ok": True, "questions": questions})
    except Exception as e:
        logger.error(f"学习批量生成失败: {e}")
        return jsonify({"ok": True, "questions": []})


@app.route('/api/learn/question', methods=['POST'])
def learn_question():
    """生成一道三选一学习题（CATTI 2-3 级）"""
    if not deepseek_client.get_api_key():
        return jsonify({"error": "请先设置 API Key"}), 400

    data = request.get_json() or {}
    level = data.get('level', 'catti3')
    learn_type = data.get('type', 'word')  # 'word' 或 'sentence'

    if learn_type == 'word':
        existing = db.get_words(limit=500)
        existing_list = [w['russian'] for w in existing]
        result = deepseek_client.generate_word_question(level, existing_list)
        chinese = result['chinese']
        # 用已有单词的翻译做干扰项
        others = [w['chinese'] for w in existing if w['chinese'] and w['chinese'] != chinese]
        if len(others) >= 2:
            distractors = random.sample(others, 2)
        else:
            # AI 生成干扰翻译
            try:
                distractors = deepseek_client.generate_distractors(result['russian'], chinese)
            except Exception:
                distractors = ['[选项A]', '[选项B]']

        options = [chinese] + distractors
        random.shuffle(options)
        correct_index = options.index(chinese)

    else:
        existing = db.get_sentences(limit=500)
        existing_list = [s['corrected'] or s['original'] for s in existing]
        result = deepseek_client.generate_sentence_question(level, existing_list)
        chinese = result['chinese']
        try:
            distractors = deepseek_client.generate_distractors(result['russian'], chinese)
        except Exception:
            distractors = ['[选项A]', '[选项B]']

        options = [chinese] + distractors
        random.shuffle(options)
        correct_index = options.index(chinese)

    return jsonify({
        "ok": True,
        "russian": result['russian'],
        "options": options,
        "correct_index": correct_index,
        "type": learn_type,
    })


@app.route('/api/learn/check', methods=['POST'])
def learn_check():
    """检查答案，答错自动录入数据库"""
    data = request.get_json()
    russian = data.get('russian', '').strip()
    chosen = data.get('chosen', -1)
    correct_index = data.get('correct_index', -1)
    options = data.get('options', [])
    learn_type = data.get('type', 'word')

    is_correct = (chosen == correct_index)
    correct_chinese = options[correct_index] if 0 <= correct_index < len(options) else ''

    saved = False
    if correct_chinese:
        if learn_type == 'word':
            if not db.word_exists(russian):
                db.add_word(russian, correct_chinese, [])
                saved = True
        else:
            if not db.sentence_exists(russian):
                db.add_sentence(russian, russian, correct_chinese, [])
                saved = True

    return jsonify({
        "is_correct": is_correct,
        "correct_index": correct_index,
        "correct_chinese": correct_chinese,
        "saved": saved,
    })


# ─── 统计 API ─────────────────────────────────────────────────

@app.route('/api/logs', methods=['GET'])
def get_logs():
    """返回最近 80 行日志"""
    lines = request.args.get('lines', 80, type=int)
    try:
        if os.path.exists(logger.LOG_FILE):
            with open(logger.LOG_FILE, encoding='utf-8') as f:
                all_lines = f.readlines()
                return jsonify({"log": ''.join(all_lines[-lines:])})
    except Exception:
        pass
    return jsonify({"log": "暂无日志"})


@app.route('/api/version', methods=['GET'])
def get_version():
    return jsonify({"version": "1.09"})


@app.route('/api/stats', methods=['GET'])
def get_stats():
    stats = db.get_stats()
    return jsonify(stats)


# ─── 启动 ─────────────────────────────────────────────────────

def _open_browser():
    """延迟打开浏览器"""
    webbrowser.open('http://127.0.0.1:8910')


def main():
    logger.info("小陈陈的俄语单词本 启动")
    db.init_db()
    logger.info(f"数据库路径: {db.DB_PATH}")
    # 启动时加载持久化的 API Key
    saved_key = _load_api_key()
    if saved_key:
        deepseek_client.set_api_key(saved_key)
    print("📖 小陈陈的俄语单词本 已启动")
    print("   打开浏览器访问 http://127.0.0.1:8910")
    # 自动打开浏览器
    threading.Timer(1.0, _open_browser).start()
    app.run(host='127.0.0.1', port=8910, debug=False)


if __name__ == '__main__':
    main()
