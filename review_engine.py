"""
俄语单词本 — 复习引擎
加权随机出题，优先考察错误率高的单词/句式
"""

import random
import db
import deepseek_client


def _weight(item: dict) -> float:
    """
    计算条目的复习权重
    权重 = (wrong_count + 1) / (correct_count + wrong_count + 2)

    两条核心规则：
    1. 错误次数越多 → 权重越高（分子增大）
    2. 总做题次数越多 → 权重越低（分母增大，见过太多次就降权）

    - 新词 (0,0): 0.50 — 中等优先
    - 常错少见 (5,1): 0.75 — 最高优先
    - 常错常见 (5,10): 0.35 — 错多但见太多了，降权
    - 全对 (0,10): 0.08 — 几乎不出现但不遗忘
    """
    w = item.get('wrong_count', 0)
    c = item.get('correct_count', 0)
    return (w + 1) / (c + w + 2)


def _weighted_choice(items: list[dict]) -> dict:
    """按权重随机选择一个 item"""
    if not items:
        return None
    weights = [_weight(it) for it in items]
    total = sum(weights)
    r = random.random() * total
    cumulative = 0
    for i, w in enumerate(weights):
        cumulative += w
        if r <= cumulative:
            return items[i]
    return items[-1]


def _generate_options(correct_item: dict, all_items: list[dict], key_field: str, count: int = 3) -> list[str]:
    """
    生成选择题选项（含 1 个正确 + 2 个干扰项）
    过滤掉与正确答案值相同的干扰项，避免重复选项
    """
    correct_value = correct_item[key_field]
    # 从其他条目中选干扰项，排除翻译相同的
    others = [it for it in all_items if it['id'] != correct_item['id'] and it[key_field] != correct_value]
    if len(others) < count - 1:
        distractors = [it[key_field] for it in others]
    else:
        distractors = [it[key_field] for it in random.sample(others, count - 1)]

    options = [correct_value] + distractors
    # 二次去重（安全网）
    seen = set()
    unique = []
    for o in options:
        if o not in seen:
            seen.add(o)
            unique.append(o)
    random.shuffle(unique)
    return unique


def select_question() -> dict | None:
    """
    选择一道复习题
    返回格式:
    {
        "type": "word_ru_to_zh",    # 题目类型
        "question": "книга",         # 题干
        "options": ["书", "桌子", "窗户"],  # 选项（已打乱）
        "correct_index": 0,          # 正确答案在 options 中的索引
        "item_id": 1,               # 条目 id
        "table": "words",           # 所属表
        "question_label": "请选择 'книга' 的中文意思"
    }
    """
    data = db.get_all_items()
    words = data['words']
    sentences = data['sentences']

    if not words and not sentences:
        return None

    # 决定题目类型：优先有数据的类型
    types = []
    if words:
        types.extend(['word_ru_to_zh', 'word_zh_to_ru'])
    if sentences:
        types.extend(['sentence_ru_to_zh'])

    if not types:
        return None

    qtype = random.choice(types)

    if qtype in ('word_ru_to_zh', 'word_zh_to_ru'):
        correct = _weighted_choice(words)
        if not correct:
            return None

        if qtype == 'word_ru_to_zh':
            question = correct['russian']
            correct_answer = correct['chinese']
            if not correct_answer:
                correct_answer = correct['russian']
            options = _generate_options(correct, words, 'chinese')
            if not options:
                return None
            question_label = f"请选择 '{question}' 的中文意思"
        else:
            question = correct['chinese']
            if not question:
                question = correct['russian']
            correct_answer = correct['russian']
            options = _generate_options(correct, words, 'russian')
            if not options:
                return None
            question_label = f"请选择 '{question}' 对应的俄语单词"

        # 确保正确答案在选项中
        try:
            correct_index = options.index(correct_answer)
        except ValueError:
            options[0] = correct_answer
            correct_index = 0

        return {
            "type": qtype,
            "question": question,
            "options": options,
            "correct_index": correct_index,
            "item_id": correct['id'],
            "table": "words",
            "question_label": question_label,
        }

    elif qtype == 'sentence_ru_to_zh':
        correct = _weighted_choice(sentences)
        if not correct:
            return None

        question = correct['corrected'] or correct['original']
        correct_answer = correct['chinese']
        if not correct_answer:
            correct_answer = question

        # 优先使用缓存干扰项
        cached = db.get_sentence_distractors(correct['id'])
        if cached and len(cached) >= 2:
            options = [correct_answer] + cached
            random.shuffle(options)
        else:
            # 尝试 AI 生成干扰项
            try:
                if deepseek_client.get_api_key():
                    ai_distractors = deepseek_client.generate_distractors(question, correct_answer)
                    if ai_distractors and len(ai_distractors) >= 2:
                        db.save_sentence_distractors(correct['id'], ai_distractors[:2])
                        options = [correct_answer] + ai_distractors[:2]
                        random.shuffle(options)
                    else:
                        options = _generate_options(correct, sentences, 'chinese')
                else:
                    options = _generate_options(correct, sentences, 'chinese')
            except Exception:
                options = _generate_options(correct, sentences, 'chinese')

        if not options or len(options) < 2:
            return None

        question_label = f"请选择俄语句子的中文翻译"

        try:
            correct_index = options.index(correct_answer)
        except ValueError:
            options[0] = correct_answer
            correct_index = 0

        return {
            "type": qtype,
            "question": question,
            "options": options,
            "correct_index": correct_index,
            "item_id": correct['id'],
            "table": "sentences",
            "question_label": question_label,
        }

    return None
