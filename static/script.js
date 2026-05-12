/**
 * 俄语单词本 — 前端逻辑
 */

// ─── 全局状态 ───────────────────────────
let reviewQuestion = null;  // 当前复习题
let reviewCount = 0;       // 本轮已答题数
let reviewCorrect = 0;     // 本轮正确数
const REVIEW_ROUND = 10;   // 每轮题数
const THEME_STORAGE_KEY = 'russian_wordbook_theme';

// ─── 初始化 ─────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTheme();
  initTabs();
  initSettings();
  initAddEntry();
  initReview();
  initDedupButtons();
  initLearn();
  initFeedback();
  initHeartbeat();
  checkSettings();
  loadVersion();
});

// ─── Tab 切换 ──────────────────────────
function initTabs() {
  document.querySelectorAll('.tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      tab.classList.add('active');
      const target = document.getElementById('tab-' + tab.dataset.tab);
      if (target) target.classList.add('active');

      // 切换到列表页时自动加载
      if (tab.dataset.tab === 'word-list') loadWords();
      if (tab.dataset.tab === 'sentence-list') loadSentences();
      if (tab.dataset.tab === 'review') loadReviewStats();
    });
  });
}

// ─── API 封装 ──────────────────────────
async function api(method, url, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch(url, opts);
  return resp.json();
}

function initHeartbeat() {
  const send = () => {
    fetch('/api/heartbeat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: '{}',
      keepalive: true,
    }).catch(() => {});
  };
  send();
  setInterval(send, 10000);
}

function escapeHtml(value) {
  return String(value ?? '').replace(/[&<>"']/g, c => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#39;',
  }[c]));
}

function initTheme() {
  const select = document.getElementById('theme-select');
  if (!select) return;

  const validThemes = new Set(['light', 'dark', 'eye']);
  let theme = 'light';

  try {
    const saved = localStorage.getItem(THEME_STORAGE_KEY);
    if (saved && validThemes.has(saved)) {
      theme = saved;
    }
  } catch (e) {}

  select.value = theme;
  applyTheme(theme);

  select.addEventListener('change', () => {
    const nextTheme = validThemes.has(select.value) ? select.value : 'light';
    applyTheme(nextTheme);
    try {
      localStorage.setItem(THEME_STORAGE_KEY, nextTheme);
    } catch (e) {}
  });
}

function applyTheme(theme) {
  document.body.setAttribute('data-theme', theme);
}

// ─── 设置 ──────────────────────────────
function initSettings() {
  // 点击状态徽章打开设置弹窗
  document.getElementById('api-status-btn').addEventListener('click', () => {
    document.getElementById('settings-overlay').style.display = 'flex';
    document.getElementById('settings-msg').textContent = '';
  });

  // 关闭弹窗
  document.getElementById('close-settings-btn').addEventListener('click', () => {
    document.getElementById('settings-overlay').style.display = 'none';
  });

  // 点击遮罩关闭
  document.getElementById('settings-overlay').addEventListener('click', (e) => {
    if (e.target === document.getElementById('settings-overlay')) {
      document.getElementById('settings-overlay').style.display = 'none';
    }
  });

  // 保存 API Key
  document.getElementById('save-key-btn').addEventListener('click', async () => {
    const key = document.getElementById('api-key-input').value.trim();
    if (!key) return;

    const saveResult = await api('POST', '/api/settings', { api_key: key });
    updateApiStatus(true);

    // 检查是否持久化成功
    const msg = document.getElementById('settings-msg');
    if (!saveResult.persisted) {
      msg.textContent = '⚠️ 保存到本地失败，重启后将丢失';
      setTimeout(() => {
        document.getElementById('settings-overlay').style.display = 'none';
      }, 2000);
      return;
    }

    // 自动补译未翻译的单词
    msg.textContent = '正在补译已有单词...';

    try {
      const result = await api('POST', '/api/words/retro-translate');
      if (result.translated > 0) {
        msg.textContent = `✅ 已补译 ${result.translated} 个单词`;
      } else if (result.failures > 0) {
        msg.textContent = `⚠️ 补译失败 (${result.failures}/${result.total})，请检查 API Key`;
      } else {
        msg.textContent = '✅ API Key 已激活';
      }
    } catch (e) {
      msg.textContent = '⚠️ 补译请求失败，请检查网络';
    }

    // 关闭弹窗
    setTimeout(() => {
      document.getElementById('settings-overlay').style.display = 'none';
      // 刷新单词列表（如果在单词库页面）
      if (document.getElementById('tab-word-list').classList.contains('active')) {
        loadWords();
      }
    }, 1500);
  });
}

function updateApiStatus(active) {
  const btn = document.getElementById('api-status-btn');
  const icon = document.getElementById('api-status-icon');
  const text = document.getElementById('api-status-text');
  if (active) {
    btn.classList.add('active');
    icon.textContent = '✅';
    text.textContent = '已激活';
  } else {
    btn.classList.remove('active');
    icon.textContent = '⚠️';
    text.textContent = '未激活';
  }
}

async function loadVersion() {
  try {
    const data = await api('GET', '/api/version');
    document.getElementById('version-text').textContent = 'v' + data.version;
  } catch (e) {}
}

async function checkSettings() {
  const data = await api('GET', '/api/settings');
  updateApiStatus(data.has_key);
}

// ─── 统一录入 ──────────────────────────
function initAddEntry() {
  const input = document.getElementById('entry-input');
  const btn = document.getElementById('add-entry-btn');

  btn.addEventListener('click', () => addEntry());
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') addEntry();
  });

  // 搜索框绑定
  document.getElementById('word-search').addEventListener('input', () => loadWords());
  document.getElementById('sentence-search').addEventListener('input', () => loadSentences());
}

async function addEntry() {
  const input = document.getElementById('entry-input');
  const text = input.value.trim();
  if (!text) return;

  const btn = document.getElementById('add-entry-btn');
  btn.disabled = true;
  btn.textContent = '处理中...';

  const result = await api('POST', '/api/entry', { text });

  const area = document.getElementById('entry-result');
  if (result.error) {
    area.innerHTML = `<div class="error-msg">${escapeHtml(result.error)}</div>`;
  } else if (result.type === 'word') {
    let exHtml = '';
    if (result.examples && result.examples.length > 0) {
      exHtml = '<div class="examples">' +
        result.examples.map(e => `<div class="example-item">📖 ${escapeHtml(e.ru)}<br>　 ${escapeHtml(e.zh)}</div>`).join('') +
        '</div>';
    }
    area.innerHTML = `
      ${result.is_corrected ? `<div class="corrected-note">✏️ 拼写已修正：</div>` : ''}
      <div class="word-display">${escapeHtml(result.russian)}</div>
      ${result.is_corrected ? `<div class="original-note">原始：${escapeHtml(result.original)}</div>` : ''}
      <div class="chinese-display">${escapeHtml(result.chinese)}</div>
      ${exHtml}
      <div class="success-note">✅ 已添加到单词库</div>
    `;
  } else {
    let exHtml = '';
    if (result.examples && result.examples.length > 0) {
      exHtml = '<div class="examples">' +
        result.examples.map(e => `<div class="example-item">💡 ${escapeHtml(e.ru)}<br>　 ${escapeHtml(e.zh)}</div>`).join('') +
        '</div>';
    }
    area.innerHTML = `
      ${result.is_corrected ? `<div class="corrected-note">✏️ 语法已修正：</div>` : ''}
      <div class="word-display">${escapeHtml(result.corrected)}</div>
      ${result.is_corrected ? `<div class="original-note">原始：${escapeHtml(result.original)}</div>` : ''}
      <div class="chinese-display">${escapeHtml(result.chinese)}</div>
      ${exHtml}
      <div class="success-note">✅ 已添加到句式库</div>
    `;
  }

  input.value = '';
  input.focus();
  btn.disabled = false;
  btn.textContent = '录入';
}

// ─── 单词库 ────────────────────────────
async function loadWords() {
  const query = document.getElementById('word-search').value.trim();
  const data = await api('GET', '/api/words' + (query ? `?search=${encodeURIComponent(query)}` : ''));
  const container = document.getElementById('word-list-container');
  document.getElementById('word-count').textContent = `${data.words.length} 个单词`;

  if (data.words.length === 0) {
    container.innerHTML = '<div class="empty-state">暂无单词，去「录入」添加吧</div>';
    return;
  }

  container.innerHTML = data.words.map(w => {
    let exHtml = '';
    if (w.examples && w.examples.length > 0) {
      exHtml = '<div class="item-examples">' +
        w.examples.map(e => `📖 ${escapeHtml(e.ru)}<br>　 ${escapeHtml(e.zh)}`).join('<br>') +
        '</div>';
    }
    return `
      <div class="list-item">
        <div class="item-head">
          <div>
            <div class="item-main">${escapeHtml(w.russian)}</div>
            <div class="item-translation">${escapeHtml(w.chinese)}</div>
          </div>
          <button class="btn-small btn-danger" onclick="deleteWord(${Number(w.id)})">删除</button>
        </div>
        ${exHtml}
        <div class="item-stats">
          <span class="correct">✅ ${Number(w.correct_count) || 0}</span>
          <span class="wrong">❌ ${Number(w.wrong_count) || 0}</span>
        </div>
      </div>
    `;
  }).join('');
}

// ─── 合并重复 ──────────────────────────
function initDedupButtons() {
  document.getElementById('dedup-words-btn').addEventListener('click', async () => {
    if (!confirm('合并重复单词？会保留翻译最完整的，合并答题统计')) return;
    const r = await api('POST', '/api/words/dedup');
    alert(`已移除 ${r.removed} 个重复单词`);
    loadWords();
  });

  document.getElementById('dedup-sentences-btn').addEventListener('click', async () => {
    if (!confirm('合并重复句式？会保留翻译最完整的，合并答题统计')) return;
    const r = await api('POST', '/api/sentences/dedup');
    alert(`已移除 ${r.removed} 个重复句式`);
    loadSentences();
  });

  document.getElementById('retro-examples-btn').addEventListener('click', async () => {
    if (!confirm('为缺少例句的单词批量生成例句？会调用 DeepSeek API')) return;

    // 显示进度遮罩（隐藏设置表单）
    const overlay = document.getElementById('settings-overlay');
    const modal = document.querySelector('.settings-modal');
    const h3 = modal.querySelector('h3');
    const hint = modal.querySelector('.hint');
    const input = document.getElementById('api-key-input');
    const actions = document.querySelector('.settings-actions');
    const msg = document.getElementById('settings-msg');

    h3.style.display = 'none';
    hint.style.display = 'none';
    input.style.display = 'none';
    actions.style.display = 'none';
    overlay.style.display = 'flex';
    msg.innerHTML = '正在检查... <button id="abort-examples-btn" class="btn-small btn-muted progress-stop-btn">停止</button>';
    let aborted = false;
    document.getElementById('abort-examples-btn').addEventListener('click', () => { aborted = true; });

    const list = await api('POST', '/api/words/retro-examples');
    const restoreSettings = () => {
      h3.style.display = '';
      hint.style.display = '';
      input.style.display = '';
      actions.style.display = '';
    };

    if (!list.words || list.words.length === 0) {
      msg.innerHTML = '✅ 所有单词已有例句';
      setTimeout(() => { overlay.style.display = 'none'; restoreSettings(); }, 1500);
      return;
    }

    let done = 0;
    const total = list.words.length;
    for (const w of list.words) {
      if (aborted) break;
      msg.innerHTML = `⏳ 正在生成例句（${done + 1}/${total}）<br><span class="progress-word">${escapeHtml(w.russian)}</span><br><button id="abort-examples-btn" class="btn-small btn-muted progress-stop-btn">停止</button>`;
      document.getElementById('abort-examples-btn').addEventListener('click', () => { aborted = true; });
      await api('POST', `/api/words/retro-example/${w.id}`);
      done++;
    }

    msg.innerHTML = aborted
      ? `⏹ 已停止（已完成 ${done}/${total}）`
      : `✅ 完成！已为 ${done} 个单词生成例句`;
    setTimeout(() => { overlay.style.display = 'none'; restoreSettings(); }, 1500);
    loadWords();
  });

  document.getElementById('retro-correct-btn').addEventListener('click', async () => {
    if (!confirm('一键纠正所有句式的语法？会调用 DeepSeek API')) return;
    const r = await api('POST', '/api/sentences/retro-correct');
    alert(`已纠正 ${r.corrected}/${r.total} 个句式`);
    loadSentences();
  });
}

async function deleteWord(id) {
  if (!confirm('确定删除这个单词吗？')) return;
  await api('DELETE', `/api/words/${id}`);
  loadWords();
}

// ─── 句式库 ────────────────────────────
async function loadSentences() {
  const query = document.getElementById('sentence-search').value.trim();
  const data = await api('GET', '/api/sentences' + (query ? `?search=${encodeURIComponent(query)}` : ''));
  const container = document.getElementById('sentence-list-container');
  document.getElementById('sentence-count').textContent = `${data.sentences.length} 个句式`;

  if (data.sentences.length === 0) {
    container.innerHTML = '<div class="empty-state">暂无句式，去「录入」添加吧</div>';
    return;
  }

  container.innerHTML = data.sentences.map(s => {
    const isCorrected = s.corrected !== s.original;
    let exHtml = '';
    if (s.examples && s.examples.length > 0) {
      exHtml = '<div class="item-examples">' +
        s.examples.map(e => `💡 ${escapeHtml(e.ru)}<br>　 ${escapeHtml(e.zh)}`).join('<br>') +
        '</div>';
    }
    return `
      <div class="list-item">
        <div class="item-head">
          <div>
            <div class="item-main">${escapeHtml(s.corrected || s.original)}</div>
            ${isCorrected ? `<div class="sentence-original">原始：${escapeHtml(s.original)}</div>` : ''}
            <div class="item-translation">${escapeHtml(s.chinese)}</div>
          </div>
          <button class="btn-small btn-danger" onclick="deleteSentence(${Number(s.id)})">删除</button>
        </div>
        ${exHtml}
        <div class="item-stats">
          <span class="correct">✅ ${Number(s.correct_count) || 0}</span>
          <span class="wrong">❌ ${Number(s.wrong_count) || 0}</span>
        </div>
      </div>
    `;
  }).join('');
}

async function deleteSentence(id) {
  if (!confirm('确定删除这个句式吗？')) return;
  await api('DELETE', `/api/sentences/${id}`);
  loadSentences();
}

// ─── 复习模式 ──────────────────────────
async function loadReviewStats() {
  const stats = await api('GET', '/api/stats');
  document.getElementById('review-stats').innerHTML =
    `📊 共 ${stats.total_words} 个单词，${stats.total_sentences} 个句式`;
}

function initReview() {
  document.getElementById('start-review-btn').addEventListener('click', startReview);
  document.getElementById('stop-review-btn').addEventListener('click', () => {
    const rate = reviewCount > 0 ? Math.round(reviewCorrect / reviewCount * 100) : 0;
    let cheer = '';
    if (rate >= 80) cheer = '🌟 太棒了！';
    else if (rate >= 60) cheer = '👍 不错！';
    else if (reviewCount > 0) cheer = '💪 继续加油！';
    document.getElementById('question-label').textContent = '';
    document.getElementById('question-text').textContent =
      `${cheer} ⏹ 已停止 ✅ ${reviewCorrect} / ${reviewCount}`;
    document.getElementById('options-container').innerHTML = '';
    document.getElementById('review-feedback').innerHTML =
      `<button class="btn-primary" onclick="startReview()">再来一轮</button>`;
    document.getElementById('review-feedback').className = '';
    document.getElementById('stop-review-btn').style.display = 'none';
  });
}

async function startReview() {
  reviewCount = 0;
  reviewCorrect = 0;
  document.getElementById('review-start').style.display = 'none';
  document.getElementById('review-question').style.display = 'block';
  await loadNextQuestion();
}

async function loadNextQuestion() {
  const data = await api('POST', '/api/review/start');
  if (data.done) {
    document.getElementById('question-label').textContent = '';
    document.getElementById('question-text').textContent = '暂无复习内容';
    document.getElementById('options-container').innerHTML = '';
    document.getElementById('review-feedback').innerHTML =
      '<button class="btn-primary" onclick="startReview()">再试一次</button>';
    document.getElementById('review-feedback').className = '';
    document.getElementById('stop-review-btn').style.display = 'none';
    return;
  }
  renderQuestion(data.question);
}

function renderQuestion(q) {
  reviewQuestion = q;
  document.getElementById('question-label').textContent =
    `第 ${reviewCount + 1}/${REVIEW_ROUND} 题 — ${q.question_label}`;
  document.getElementById('question-text').textContent = q.question;

  const container = document.getElementById('options-container');
  const labels = ['A', 'B', 'C'];
  container.innerHTML = q.options.map((opt, i) => `
    <button class="option-btn" data-index="${i}" onclick="submitAnswer(${i})">
      ${labels[i]}. ${escapeHtml(opt)}
    </button>
  `).join('');

  const fb = document.getElementById('review-feedback');
  fb.innerHTML = '';
  fb.className = '';
  document.getElementById('stop-review-btn').style.display = '';
  document.getElementById('review-question').style.display = 'block';
}

async function submitAnswer(chosen) {
  if (!reviewQuestion) return;

  reviewCount++;
  if (chosen === reviewQuestion.correct_index) reviewCorrect++;

  // 禁用选项按钮
  document.querySelectorAll('.option-btn').forEach(b => b.disabled = true);

  // 高亮正确答案和用户选择
  const correctIdx = reviewQuestion.correct_index;
  const buttons = document.querySelectorAll('.option-btn');
  buttons[correctIdx].classList.add('correct-choice');
  if (chosen !== correctIdx) {
    buttons[chosen].classList.add('wrong-choice');
  }

  // 提交答案
  const result = await api('POST', '/api/review/answer', {
    item_id: reviewQuestion.item_id,
    table: reviewQuestion.table,
    chosen: chosen,
    correct_index: correctIdx,
  });

  // 显示反馈
  const fb = document.getElementById('review-feedback');
  if (result.is_correct) {
    fb.className = 'correct-fb';
    fb.textContent = '✅ 正确！';
  } else {
    fb.className = 'wrong-fb';
    fb.textContent = '❌ 错误！';
  }

  // 0.8 秒后加载下一题或结束本轮
  setTimeout(() => {
    if (reviewCount >= REVIEW_ROUND) {
      const rate = Math.round(reviewCorrect / REVIEW_ROUND * 100);
      let cheer = '';
      if (rate >= 80) cheer = '🌟 太棒了！';
      else if (rate >= 60) cheer = '👍 不错！';
      else cheer = '💪 继续加油！';
      document.getElementById('question-label').textContent = '';
      document.getElementById('question-text').textContent =
        `${cheer} 本轮完成 ✅ ${reviewCorrect} / ${REVIEW_ROUND}`;
      document.getElementById('options-container').innerHTML = '';
      document.getElementById('review-feedback').innerHTML =
        `<button class="btn-primary" onclick="startReview()">再来一轮</button>`;
      document.getElementById('stop-review-btn').style.display = 'none';
    } else if (result.done) {
      document.getElementById('question-label').textContent = '';
      document.getElementById('question-text').textContent = '🎉 暂无内容，请先录入';
      document.getElementById('options-container').innerHTML = '';
      document.getElementById('review-feedback').innerHTML =
        `<button class="btn-primary" onclick="startReview()">再来一轮</button>`;
      document.getElementById('stop-review-btn').style.display = 'none';
    } else if (result.next_question) {
      renderQuestion(result.next_question);
    } else {
      document.getElementById('question-label').textContent = '';
      document.getElementById('question-text').textContent = '🎉 暂无更多';
      document.getElementById('options-container').innerHTML = '';
      document.getElementById('review-feedback').innerHTML =
        `<button class="btn-primary" onclick="startReview()">再来一轮</button>`;
      document.getElementById('stop-review-btn').style.display = 'none';
    }
  }, 800);
}

// ─── 学习 ──────────────────────────────
let learnState = null;  // {russian, options, correct_index, type}

function initLearn() {
  document.querySelectorAll('.learn-tab').forEach(tab => {
    tab.addEventListener('click', async () => {
      const nextType = tab.dataset.learn;
      if (nextType === learnTypeCache) return;

      if (learnState) {
        learnStateCache[learnTypeCache] = learnState;
      }

      document.querySelectorAll('.learn-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      learnTypeCache = nextType;

      if (isLearnRunning()) {
        await switchLearnType(nextType);
      }
    });
  });

  document.getElementById('start-learn-btn').addEventListener('click', startLearn);
  document.getElementById('learn-next-btn').addEventListener('click', nextLearnQuestion);
  document.getElementById('stop-learn-btn').addEventListener('click', stopLearn);
  document.getElementById('learn-level').addEventListener('change', onLearnLevelChange);
}

let learnTotal = 0;
let learnCorrect = 0;
let learnPool = { word: [], sentence: [] };
let learnStateCache = { word: null, sentence: null };
let learnTypeCache = 'word';
let learnLevelCache = 'catti3';
let poolLoading = { word: false, sentence: false };
let learnAutoNextTimer = null;
const LEARN_INITIAL_COUNT = 3;
const LEARN_REFILL_COUNT = 8;
const LEARN_LOW_WATER = 3;

function isLearnRunning() {
  return document.getElementById('learn-question-area').style.display !== 'none'
    && document.getElementById('start-learn-btn').style.display === 'none';
}

function clearLearnAutoNext() {
  if (learnAutoNextTimer) {
    clearTimeout(learnAutoNextTimer);
    learnAutoNextTimer = null;
  }
}

function showLearnLoading(message = '正在生成题目') {
  const questionEl = document.getElementById('learn-question-text');
  questionEl.classList.remove('long-question');
  questionEl.innerHTML = `
    <span class="loading-text">${escapeHtml(message)}<span class="loading-dots"><span></span><span></span><span></span></span></span>
    <span class="loading-bar"></span>
  `;
}

async function fillLearnPool(count = LEARN_REFILL_COUNT, requestType = learnTypeCache, requestLevel = learnLevelCache) {
  if (poolLoading[requestType]) return 0;
  poolLoading[requestType] = true;
  const beforeCount = learnPool[requestType].length;
  let timeout = null;
  try {
    const controller = new AbortController();
    timeout = setTimeout(() => controller.abort(), 25000);
    const resp = await fetch('/api/learn/batch', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ level: requestLevel, type: requestType, count }),
      signal: controller.signal,
    });
    const result = await resp.json();
    // 丢弃过期请求：避免切换难度后旧难度题目混入题池
    if (requestLevel !== learnLevelCache) {
      return 0;
    }
    if (result.questions) {
      learnPool[requestType].push(...result.questions);
    }
  } catch (e) {}
  if (timeout) clearTimeout(timeout);
  poolLoading[requestType] = false;
  return learnPool[requestType].length - beforeCount;
}

function nextFromPool() {
  const pool = learnPool[learnTypeCache];
  if (pool.length === 0) return null;
  return pool.shift();
}

async function startLearn() {
  clearLearnAutoNext();
  learnTotal = 0;
  learnCorrect = 0;
  poolLoading = { word: false, sentence: false };
  learnTypeCache = document.querySelector('.learn-tab.active').dataset.learn;
  learnLevelCache = document.getElementById('learn-level').value;

  // 清空当前类型的旧池
  learnPool[learnTypeCache] = [];
  learnStateCache[learnTypeCache] = null;

  document.getElementById('start-learn-btn').style.display = 'none';
  document.getElementById('learn-question-area').style.display = 'block';
  document.getElementById('learn-feedback').innerHTML = '';
  document.getElementById('learn-feedback').className = '';
  document.getElementById('learn-next-btn').style.display = 'none';
  document.getElementById('stop-learn-btn').style.display = '';
  showLearnLoading();
  document.getElementById('learn-options').innerHTML = '';

  // 首屏只生成少量题，先把第一题显示出来；后续题目后台补充。
  if (learnPool[learnTypeCache].length === 0) {
    await fillLearnPool(LEARN_INITIAL_COUNT);
  }

  const q = nextFromPool() || (await fillLearnPool(), nextFromPool());
  if (!q) {
    document.getElementById('start-learn-btn').style.display = '';
    document.getElementById('learn-question-text').textContent = '出题失败，请检查网络或 API Key';
    document.getElementById('learn-question-text').classList.remove('long-question');
    document.getElementById('learn-options').innerHTML = '';
    return;
  }

  // 后台补充池子
  if (learnPool[learnTypeCache].length < LEARN_LOW_WATER) fillLearnPool(LEARN_REFILL_COUNT);

  learnState = q;
  learnStateCache[learnTypeCache] = q;
  showLearnQuestion(q);
}

async function switchLearnType(nextType) {
  clearLearnAutoNext();
  learnTypeCache = nextType;
  learnLevelCache = document.getElementById('learn-level').value;
  document.getElementById('learn-feedback').innerHTML = '';
  document.getElementById('learn-feedback').className = '';
  document.getElementById('learn-next-btn').style.display = 'none';
  document.getElementById('stop-learn-btn').style.display = '';

  const cached = learnStateCache[nextType];
  if (cached) {
    learnState = cached;
    showLearnQuestion(cached);
    return;
  }

  let q = nextFromPool();
  if (!q) {
    showLearnLoading();
    document.getElementById('learn-options').innerHTML = '';
    await fillLearnPool(LEARN_INITIAL_COUNT, nextType, learnLevelCache);
    q = nextFromPool();
  }

  if (q) {
    learnState = q;
    learnStateCache[nextType] = q;
    showLearnQuestion(q);
    if (learnPool[nextType].length < LEARN_LOW_WATER) {
      fillLearnPool(LEARN_REFILL_COUNT, nextType, learnLevelCache);
    }
  } else {
    learnState = null;
    document.getElementById('learn-question-text').textContent = '出题失败，请检查网络或 API Key';
    document.getElementById('learn-question-text').classList.remove('long-question');
    document.getElementById('learn-options').innerHTML = '';
  }
}

async function nextLearnQuestion() {
  document.getElementById('learn-next-btn').style.display = 'none';
  document.getElementById('learn-feedback').innerHTML = '';
  document.getElementById('learn-feedback').className = '';
  document.getElementById('stop-learn-btn').style.display = '';

  if (learnPool[learnTypeCache].length === 0) {
    showLearnLoading('正在补充题目');
    document.getElementById('learn-options').innerHTML = '';
    await fillLearnPool(LEARN_INITIAL_COUNT);
  }

  const q = nextFromPool();
  if (q) {
    learnState = q;
    learnStateCache[learnTypeCache] = q;
    showLearnQuestion(q);
    if (learnPool[learnTypeCache].length < LEARN_LOW_WATER) {
      fillLearnPool(LEARN_REFILL_COUNT);
    }
  } else {
    document.getElementById('start-learn-btn').style.display = '';
    document.getElementById('learn-question-area').style.display = 'none';
  }
}

function showLearnQuestion(q) {
  document.getElementById('learn-next-btn').style.display = 'none';
  const questionEl = document.getElementById('learn-question-text');
  questionEl.textContent = q.russian;
  questionEl.classList.toggle('long-question', isLongQuestion(q.russian));
  const labels = ['A', 'B', 'C'];
  document.getElementById('learn-options').innerHTML = q.options.map((opt, i) => `
    <button class="option-btn" onclick="submitLearn(${i})">${labels[i]}. ${escapeHtml(opt)}</button>
  `).join('');
}

function isLongQuestion(text) {
  const value = String(text || '').trim();
  return value.includes(' ') || value.length > 24;
}

async function submitLearn(chosen) {
  if (!learnState) return;
  document.querySelectorAll('#learn-options .option-btn').forEach(b => b.disabled = true);

  const result = await api('POST', '/api/learn/check', {
    russian: learnState.russian,
    chosen: chosen,
    correct_index: learnState.correct_index,
    options: learnState.options,
    type: learnState.type,
  });

  // 高亮
  const buttons = document.querySelectorAll('#learn-options .option-btn');
  buttons[result.correct_index].classList.add('correct-choice');
  if (chosen !== result.correct_index) {
    buttons[chosen].classList.add('wrong-choice');
  }

  learnTotal++;
  if (result.is_correct) learnCorrect++;
  learnStateCache[learnTypeCache] = null;

  const fb = document.getElementById('learn-feedback');
  if (result.is_correct) {
    fb.className = 'correct';
    fb.innerHTML = '✅ 正确！';
    clearLearnAutoNext();
    learnAutoNextTimer = setTimeout(() => {
      learnAutoNextTimer = null;
      nextLearnQuestion();
    }, 800);
  } else {
    fb.className = 'wrong';
    fb.innerHTML = `❌ 错误<br>正确：${escapeHtml(result.correct_chinese)}${result.saved ? '<br>📝 已自动录入' : ''}`;
    document.getElementById('learn-next-btn').style.display = '';
  }

  if (!result.is_correct) {
    clearLearnAutoNext();
  }
}

function stopLearn() {
  clearLearnAutoNext();
  learnState = null;
  learnStateCache[learnTypeCache] = null;
  learnPool = { word: [], sentence: [] };
  poolLoading = { word: false, sentence: false };
  const total = learnTotal;
  const correct = learnCorrect;
  const rate = total > 0 ? Math.round(correct / total * 100) : 0;

  let msg = '';
  if (total === 0) {
    msg = '还没有答题哦';
  } else if (rate >= 80) {
    msg = `🌟 太棒了！正确率 ${rate}%（${correct}/${total}）`;
  } else if (rate >= 60) {
    msg = `👍 不错！正确率 ${rate}%（${correct}/${total}），继续加油`;
  } else {
    msg = `💪 正确率 ${rate}%（${correct}/${total}），多练练会更好`;
  }

  document.getElementById('learn-question-text').textContent = msg;
  document.getElementById('learn-options').innerHTML = '';
  document.getElementById('learn-feedback').innerHTML = `<button class="btn-primary" onclick="startLearn()">继续学习</button>`;
  document.getElementById('learn-feedback').className = '';
  document.getElementById('learn-next-btn').style.display = 'none';
  document.getElementById('stop-learn-btn').style.display = 'none';
  learnTotal = 0;
  learnCorrect = 0;
}

function resetLearn() {
  learnTotal = 0;
  learnCorrect = 0;
}

async function onLearnLevelChange() {
  const nextLevel = document.getElementById('learn-level').value;
  if (nextLevel === learnLevelCache) return;
  learnLevelCache = nextLevel;

  clearLearnAutoNext();
  // 难度变更后，清空所有缓存，避免旧难度题目残留
  learnPool = { word: [], sentence: [] };
  learnStateCache = { word: null, sentence: null };
  poolLoading = { word: false, sentence: false };
  learnState = null;

  if (!isLearnRunning()) return;

  document.getElementById('learn-feedback').innerHTML = '';
  document.getElementById('learn-feedback').className = '';
  document.getElementById('learn-next-btn').style.display = 'none';
  document.getElementById('stop-learn-btn').style.display = '';
  showLearnLoading('正在切换难度并生成新题');
  document.getElementById('learn-options').innerHTML = '';

  await fillLearnPool(LEARN_INITIAL_COUNT, learnTypeCache, learnLevelCache);
  const q = nextFromPool() || (await fillLearnPool(LEARN_INITIAL_COUNT, learnTypeCache, learnLevelCache), nextFromPool());
  if (!q) {
    document.getElementById('learn-question-text').textContent = '出题失败，请检查网络或 API Key';
    document.getElementById('learn-question-text').classList.remove('long-question');
    document.getElementById('learn-options').innerHTML = '';
    return;
  }

  learnState = q;
  learnStateCache[learnTypeCache] = q;
  showLearnQuestion(q);
  if (learnPool[learnTypeCache].length < LEARN_LOW_WATER) {
    fillLearnPool(LEARN_REFILL_COUNT, learnTypeCache, learnLevelCache);
  }
}

// ─── 反馈 ──────────────────────────────
function initFeedback() {
  document.getElementById('feedback-btn').addEventListener('click', async () => {
    try {
      const data = await api('GET', '/api/logs');
      const subject = encodeURIComponent('俄语单词本 反馈');
      const body = encodeURIComponent('请描述遇到的问题：\n\n--- 日志 ---\n' + data.log);
      window.location.href = `mailto:shucarlet@gmail.com?subject=${subject}&body=${body}`;
    } catch (e) {
      window.location.href = 'mailto:shucarlet@gmail.com?subject=俄语单词本反馈';
    }
  });
}
