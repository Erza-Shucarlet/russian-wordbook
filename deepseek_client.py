"""
小陈陈的俄语单词本 — DeepSeek API 客户端
用于俄语翻译、例句生成、语法纠错
"""

import json
import requests
import logger

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
        "model": "deepseek-v4-flash",
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
    logger.debug(f"API响应: model={payload['model']} tokens_in={data.get('usage',{}).get('prompt_tokens','?')} tokens_out={data.get('usage',{}).get('completion_tokens','?')}")
    return json.loads(content)


# ─── 翻译与例句 ────────────────────────────────────────────────

def translate_word(russian_word: str) -> dict:
    """
    翻译俄语单词并生成例句
    返回: { "chinese": "...", "examples": [{"ru": "...", "zh": "..."}, ...] }
    """
    system = """你是俄语语言专家。用户给你一个俄语单词，你需要：
1. 如果是名词，必须返回一格（主格）单数形式。检查拼写是否正确，如果错误或不是一格形式，给出正确的一格拼写，corrected=true；如果已经是一格且拼写正确，russian保持原样，corrected=false
2. 给出该单词最常见的中文释义
3. 给出 2 个使用正确形式的俄语例句及中文翻译

必须以 JSON 格式返回：
{"russian": "正确拼写", "corrected": true或false, "chinese": "中文释义", "examples": [{"ru": "俄语句子", "zh": "中文翻译"}, ...]}"""

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


def generate_distractors(russian_sentence: str, correct_chinese: str) -> list:
    """为俄语句子生成 2 个接近但错误的中文干扰翻译"""
    system = """你是俄语翻译专家。给你一个俄语句子和它的正确中文翻译，请生成 2 个错误但看起来合理的中文翻译作为干扰选项。
要求：
- 干扰项要接近原意，但有关键区别（如主语、宾语、动词、时态等某个细节故意译错）
- 不能和正确翻译相同
- 以 JSON 数组格式返回：["干扰项1", "干扰项2"]"""

    return _call_deepseek(system, f"俄语句子：{russian_sentence}\n正确翻译：{correct_chinese}\n请生成 2 个干扰项")


def generate_word_batch(level: str, exclude_words: list[str], count: int = 10) -> list:
    """批量生成 CATTI 级别俄语单词题（含干扰项）"""
    level_desc = "CATTI二级（较难）" if level == 'catti2' else "CATTI三级（中等）"
    exclude_list = ','.join(exclude_words[:50]) if exclude_words else '无'

    system = f"""你是俄语教学专家。请一次生成 {count} 道{level_desc}俄语单词翻译选择题。
要求：
- 每题一个俄语单词和其正确中文翻译，再加 2 个合理但错误的中文干扰项
- 必须使用简体中文
- 中文选项要简短，优先使用 2-8 个汉字
- 单词的难度、长度应符合{level_desc}标准
- 避开已有单词：[{exclude_list}]
- 返回 JSON 数组：[{{"russian": "单词", "options": ["干扰1", "正确翻译", "干扰2"], "correct_index": 1}}]
- 正确翻译必须随机放在 options 的不同位置，correct_index 必须准确对应"""

    return _call_deepseek(system, f"请生成{count}道{level_desc}俄语单词选择题")


def generate_sentence_batch(level: str, exclude_sentences: list[str], count: int = 10) -> list:
    """批量生成 CATTI 级别俄语句式题（含干扰项）"""
    level_desc = "CATTI二级（较难）" if level == 'catti2' else "CATTI三级（中等）"
    exclude_list = '; '.join(exclude_sentences[:10]) if exclude_sentences else '无'

    system = f"""你是俄语教学专家。请一次生成 {count} 道{level_desc}俄语句子翻译选择题。
要求：
- 每题一个俄语句子和其正确中文翻译，再加 2 个合理但错误的中文干扰项
- 必须使用简体中文
- 中文选项要简洁，不要解释语法
- 句子的难度、复杂度应符合{level_desc}标准
- 避开已有句子：[{exclude_list}]
- 返回 JSON 数组：[{{"russian": "俄语句子", "options": ["干扰1", "正确翻译", "干扰2"], "correct_index": 1}}]
- 正确翻译必须随机放在 options 的不同位置，correct_index 必须准确对应"""

    return _call_deepseek(system, f"请生成{count}道{level_desc}俄语句子选择题")


def generate_word_question(level: str, exclude_words: list[str]) -> dict:
    """生成一个 CATTI 级别俄语单词题"""
    level_desc = "CATTI二级（较难）" if level == 'catti2' else "CATTI三级（中等）"
    exclude_list = ','.join(exclude_words[:50]) if exclude_words else '无'

    system = f"""你是俄语教学专家。请生成一个{level_desc}难度的俄语单词用于翻译练习。
要求：
- 随机一个单词，不要从已有列表里选：[{exclude_list}]
- 返回该单词的一格形式和一两个字的简洁中文释义
- 以 JSON 返回：{{"russian": "单词", "chinese": "中文释义"}}"""

    return _call_deepseek(system, f"请生成一个{level_desc}的俄语单词，避开：{exclude_list}")


def generate_sentence_question(level: str, exclude_sentences: list[str]) -> dict:
    """生成一个 CATTI 级别俄语句式题"""
    level_desc = "CATTI二级（较难）" if level == 'catti2' else "CATTI三级（中等）"
    exclude_list = '; '.join(exclude_sentences[:10]) if exclude_sentences else '无'

    system = f"""你是俄语教学专家。请生成一个{level_desc}难度的俄语句子用于翻译练习。
要求：
- 随机一个句子，语法正确，不要和已有句子重复
- 返回俄语句子和简洁中文翻译
- 以 JSON 返回：{{"russian": "俄语句子", "chinese": "中文翻译"}}"""

    return _call_deepseek(system, f"请生成一个{level_desc}的俄语句子，避开：{exclude_list}")


def judge_answer(russian: str, correct_chinese: str, user_answer: str) -> bool:
    """判断用户翻译是否正确"""
    system = """你是俄语翻译评判专家。给你俄语原文、标准中文翻译和用户翻译，判断用户翻译是否正确。
要求：
- 核心意思一致即可，不要求字面完全一致
- 返回 JSON：{"correct": true或false}"""

    user_msg = f"俄语：{russian}\n标准翻译：{correct_chinese}\n用户翻译：{user_answer}"
    result = _call_deepseek(system, user_msg)
    return result.get('correct', False)


def translate_sentence(russian_sentence: str) -> dict:
    """
    翻译俄语句子（用于用户手动翻译需求）
    返回: { "chinese": "..." }
    """
    system = """你是俄语翻译专家。请将用户给出的俄语句子翻译成中文。
以 JSON 格式返回：{"chinese": "中文翻译"}"""

    return _call_deepseek(system, f"请翻译：{russian_sentence}")
