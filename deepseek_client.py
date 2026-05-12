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
    system = """你是俄语语言专家。任务：把用户输入规范化为可入库的俄语单词卡。
规则：
1. 只处理“单个俄语单词”；如果不是单词，也必须尽量返回最接近的合法单词形态
2. 如果是名词，返回主格单数一格；若原词已正确则 corrected=false，否则 corrected=true
3. chinese 给出最常见、最简洁的中文义项（优先 2-8 个汉字）
4. examples 返回 2 条，且都使用你给出的 russian 形态
5. 禁止输出 Markdown、注释、解释性文本

严格输出 JSON 对象（仅这些键）：
{
  "russian": "正确拼写或规范词形",
  "corrected": true,
  "chinese": "中文释义",
  "examples": [{"ru": "俄语例句", "zh": "中文翻译"}, {"ru": "...", "zh": "..."}]
}"""

    return _call_deepseek(system, f"请翻译以下俄语单词并生成例句：{russian_word}")


def correct_sentence(russian_sentence: str) -> dict:
    """
    修正俄语句式并翻译
    返回: { "corrected": "...", "chinese": "...", "examples": [{"ru": "...", "zh": "..."}] }
    """
    system = """你是俄语语言专家。任务：纠正并翻译俄语句子。
规则：
1. corrected 返回语法正确、自然的俄语句子；若原句本身正确可保持不变
2. chinese 返回简体中文自然译文
3. examples 返回 1 条相似句式（ru+zh）
4. 禁止输出 Markdown、解释性文字

严格输出 JSON 对象（仅这些键）：
{
  "corrected": "修正后的俄语句子",
  "chinese": "中文翻译",
  "examples": [{"ru": "关联句式", "zh": "中文翻译"}]
}"""

    return _call_deepseek(system, f"请检查并修正以下俄语句子：{russian_sentence}")


def generate_distractors(russian_sentence: str, correct_chinese: str) -> list:
    """为俄语句子生成 2 个接近但错误的中文干扰翻译"""
    system = """你是俄语翻译专家。给你一个俄语句子和它的正确中文翻译，请生成 2 个错误但看起来合理的中文翻译作为干扰选项。
要求：
- 干扰项要接近原意，但有关键区别（如主语、宾语、动词、时态等某个细节故意译错）
- 不能和正确翻译相同
- 每个干扰项建议 4-18 个字
- 禁止输出 Markdown、解释性文字
- 以 JSON 对象返回：{"distractors": ["干扰项1", "干扰项2"]}"""

    result = _call_deepseek(system, f"俄语句子：{russian_sentence}\n正确翻译：{correct_chinese}\n请生成 2 个干扰项")
    if isinstance(result, dict):
        items = result.get("distractors", [])
    elif isinstance(result, list):
        items = result
    else:
        items = []
    cleaned = []
    for x in items:
        text = str(x).strip()
        if text and text != correct_chinese and text not in cleaned:
            cleaned.append(text)
    return cleaned[:2]


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
- 每题 options 必须恰好 3 项，且三项互不相同
- correct_index 必须是 0/1/2 且与正确中文严格对应
- 禁止输出 Markdown、解释性文字
- 返回 JSON 对象：
{{
  "questions": [
    {{"russian": "单词", "options": ["干扰1", "正确翻译", "干扰2"], "correct_index": 1}}
  ]
}}"""

    result = _call_deepseek(system, f"请生成{count}道{level_desc}俄语单词选择题")
    if isinstance(result, dict):
        questions = result.get("questions", [])
    elif isinstance(result, list):
        questions = result
    else:
        questions = []
    return questions if isinstance(questions, list) else []


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
- 每题 options 必须恰好 3 项，且三项互不相同
- correct_index 必须是 0/1/2 且与正确中文严格对应
- 禁止输出 Markdown、解释性文字
- 返回 JSON 对象：
{{
  "questions": [
    {{"russian": "俄语句子", "options": ["干扰1", "正确翻译", "干扰2"], "correct_index": 1}}
  ]
}}"""

    result = _call_deepseek(system, f"请生成{count}道{level_desc}俄语句子选择题")
    if isinstance(result, dict):
        questions = result.get("questions", [])
    elif isinstance(result, list):
        questions = result
    else:
        questions = []
    return questions if isinstance(questions, list) else []


def generate_word_question(level: str, exclude_words: list[str]) -> dict:
    """生成一个 CATTI 级别俄语单词题"""
    level_desc = "CATTI二级（较难）" if level == 'catti2' else "CATTI三级（中等）"
    exclude_list = ','.join(exclude_words[:50]) if exclude_words else '无'

    system = f"""你是俄语教学专家。请生成一个{level_desc}难度的俄语单词用于翻译练习。
要求：
- 随机一个单词，不要从已有列表里选：[{exclude_list}]
- 返回该单词的一格形式和简洁中文释义（2-8 个汉字）
- 禁止输出 Markdown、解释性文字
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
- 禁止输出 Markdown、解释性文字
- 以 JSON 返回：{{"russian": "俄语句子", "chinese": "中文翻译"}}"""

    return _call_deepseek(system, f"请生成一个{level_desc}的俄语句子，避开：{exclude_list}")


def judge_answer(russian: str, correct_chinese: str, user_answer: str) -> bool:
    """判断用户翻译是否正确"""
    system = """你是俄语翻译评判专家。给你俄语原文、标准中文翻译和用户翻译，判断用户翻译是否正确。
要求：
- 核心意思一致即可，不要求字面完全一致
- 只返回 JSON 对象，不要解释
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
要求：
- 使用自然、简洁的简体中文
- 只返回 JSON 对象，不要解释
返回：{"chinese": "中文翻译"}"""

    return _call_deepseek(system, f"请翻译：{russian_sentence}")
