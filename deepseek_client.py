"""
俄语单词本 — DeepSeek API 客户端
用于俄语翻译、例句生成、语法纠错
"""

import json
import requests

API_BASE = "https://api.deepseek.com/v1/chat/completions"

# 全局 API Key，由 app.py 设置
_api_key = None


def set_api_key(key: str):
    global _api_key
    _api_key = key


def get_api_key() -> str:
    return _api_key


def _call_deepseek(system_prompt: str, user_message: str, temperature: float = 0.3) -> str:
    """调用 DeepSeek API，返回文本响应"""
    if not _api_key:
        raise RuntimeError("请先设置 DeepSeek API Key")

    headers = {
        "Authorization": f"Bearer {_api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message},
        ],
        "temperature": temperature,
        "max_tokens": 1024,
        "response_format": {"type": "json_object"},
    }

    resp = requests.post(API_BASE, headers=headers, json=payload, timeout=60)
    resp.raise_for_status()
    data = resp.json()
    content = data["choices"][0]["message"]["content"]
    return json.loads(content)


# ─── 翻译与例句 ────────────────────────────────────────────────

def translate_word(russian_word: str) -> dict:
    """
    翻译俄语单词并生成例句
    返回: { "chinese": "...", "examples": [{"ru": "...", "zh": "..."}, ...] }
    """
    system = """你是俄语语言专家。用户给你一个俄语单词，你需要：
1. 给出该单词最常见的中文释义（名词给出一格形式对应的释义）
2. 给出 2 个使用该单词的俄语例句及中文翻译

必须以 JSON 格式返回：
{"chinese": "中文释义", "examples": [{"ru": "俄语句子", "zh": "中文翻译"}, ...]}"""

    return _call_deepseek(system, f"请翻译以下俄语单词并生成例句：{russian_word}")


def correct_sentence(russian_sentence: str) -> dict:
    """
    修正俄语句式并翻译
    返回: { "corrected": "...", "chinese": "...", "examples": [{"ru": "...", "zh": "..."}] }
    """
    system = """你是俄语语言专家。用户给你一个俄语句子，你需要：
1. 检查语法是否正确，如果有错误请修正；如果正确则保留原文
2. 给出该句子的中文翻译
3. 提供 1 个用法相似或关联的俄语句式及中文翻译

必须以 JSON 格式返回：
{"corrected": "修正后的俄语句子", "chinese": "中文翻译", "examples": [{"ru": "关联句式", "zh": "中文翻译"}]}"""

    return _call_deepseek(system, f"请检查并修正以下俄语句子：{russian_sentence}")


def translate_sentence(russian_sentence: str) -> dict:
    """
    翻译俄语句子（用于用户手动翻译需求）
    返回: { "chinese": "..." }
    """
    system = """你是俄语翻译专家。请将用户给出的俄语句子翻译成中文。
以 JSON 格式返回：{"chinese": "中文翻译"}"""

    return _call_deepseek(system, f"请翻译：{russian_sentence}")
