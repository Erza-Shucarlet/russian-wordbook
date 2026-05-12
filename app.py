"""
俄语单词本 — Flask 后端
支持 PyInstaller 打包后独立运行
"""

import os
import sys
import json
import webbrowser
import threading
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


@app.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')


# 其他静态文件（CSS, JS 等）
@app.route('/<path:filename>')
def static_files(filename):
    return send_from_directory(STATIC_DIR, filename)


# ─── 设置 ─────────────────────────────────────────────────────

@app.route('/api/settings', methods=['POST'])
def save_settings():
    data = request.get_json()
    key = data.get('api_key', '').strip()
    if key:
        deepseek_client.set_api_key(key)
        _save_api_key(key)
    return jsonify({"ok": True, "has_key": bool(key)})


@app.route('/api/settings', methods=['GET'])
def get_settings():
    return jsonify({"has_key": bool(deepseek_client.get_api_key())})


# ─── API Key 持久化 ───────────────────────────────────────────

def _save_api_key(key: str):
    """将 API Key 保存到本地文件"""
    try:
        os.makedirs(os.path.dirname(db.SETTINGS_PATH), exist_ok=True)
        with open(db.SETTINGS_PATH, 'w') as f:
            json.dump({"api_key": key}, f)
    except Exception:
        pass  # 写入失败不影响使用


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

@app.route('/api/words', methods=['POST'])
def add_word():
    """录入生词 — 自动调用 DeepSeek 获取翻译和例句"""
    data = request.get_json()
    russian = data.get('russian', '').strip()
    if not russian:
        return jsonify({"error": "请输入俄语单词"}), 400

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


# ─── 统计 API ─────────────────────────────────────────────────

@app.route('/api/stats', methods=['GET'])
def get_stats():
    stats = db.get_stats()
    return jsonify(stats)


# ─── 启动 ─────────────────────────────────────────────────────

def _open_browser():
    """延迟打开浏览器"""
    webbrowser.open('http://127.0.0.1:8910')


def main():
    db.init_db()
    # 启动时加载持久化的 API Key
    saved_key = _load_api_key()
    if saved_key:
        deepseek_client.set_api_key(saved_key)
    print("📖 俄语单词本 已启动")
    print("   打开浏览器访问 http://127.0.0.1:8910")
    # 自动打开浏览器
    threading.Timer(1.0, _open_browser).start()
    app.run(host='127.0.0.1', port=8910, debug=False)


if __name__ == '__main__':
    main()