/**
 * 俄语单词本 — 前端逻辑
 */

// ─── 全局状态 ───────────────────────────
let reviewQuestion = null;  // 当前复习题

// ─── 初始化 ─────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initSettings();
  initAddWord();
  initAddSentence();
  initWordList();
  initSentenceList();
  initReview();
  checkSettings();
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

// ─── 设置 ──────────────────────────────
function initSettings() {
  document.getElementById('save-key-btn').addEventListener('click', async () => {
    const key = document.getElementById('api-key-input').value.trim();
    await api('POST', '/api/settings', { api_key: key });
    const status = document.getElementById('key-status');
    status.textContent = key ? '✅' : '未设置';
  });
}

async function checkSettings() {
  const data = await api('GET', '/api/settings');
  document.getElementById('key-status').textContent = data.has_key ? '✅' : '未设置';
}

// ─── 录入生词 ──────────────────────────
function initAddWord() {
  const input = document.getElementById('word-input');
  const btn = document.getElementById('add-word-btn');

  btn.addEventListener('click', () => addWord());

  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') addWord();
  });

  // 搜索框实时搜索单词库
  const searchInput = document.getElementById('word-search');
  searchInput.addEventListener('input', () => loadWords());
}

async function addWord() {
  const input = document.getElementById('word-input');
  const russian = input.value.trim();
  if (!russian) return;

  const btn = document.getElementById('add-word-btn');
  btn.disabled = true;
  btn.textContent = '查询中...';

  const result = await api('POST', '/api/words', { russian });

  const area = document.getElementById('word-result');
  if (result.error) {
    area.innerHTML = `<div class="error-msg">${result.error}</div>`;
  } else {
    let exHtml = '';
    if (result.examples && result.examples.length > 0) {
      exHtml = '<div class="examples">' +
        result.examples.map(e => `<div class="example-item">📖 ${e.ru}<br>　 ${e.zh}</div>`).join('') +
        '</div>';
    }
    area.innerHTML = `
      <div class="word-display">${result.russian}</div>
      <div class="chinese-display">${result.chinese}</div>
      ${exHtml}
      <div style="font-size:0.8rem;color:var(--success);margin-top:6px">✅ 已添加到单词库</div>
    `;
    input.value = '';
    input.focus();
  }

  btn.disabled = false;
  btn.textContent = '录入';
}

// ─── 录入句式 ──────────────────────────
function initAddSentence() {
  const input = document.getElementById('sentence-input');
  const btn = document.getElementById('add-sentence-btn');

  btn.addEventListener('click', () => addSentence());
  input.addEventListener('keydown', (e) => {
    if (e.key === 'Enter') addSentence();
  });

  const searchInput = document.getElementById('sentence-search');
  searchInput.addEventListener('input', () => loadSentences());
}

async function addSentence() {
  const input = document.getElementById('sentence-input');
  const sentence = input.value.trim();
  if (!sentence) return;

  const btn = document.getElementById('add-sentence-btn');
  btn.disabled = true;
  btn.textContent = '处理中...';

  const result = await api('POST', '/api/sentences', { sentence });

  const area = document.getElementById('sentence-result');
  if (result.error) {
    area.innerHTML = `<div class="error-msg">${result.error}</div>`;
  } else {
    const isCorrected = result.corrected !== result.original;
    let exHtml = '';
    if (result.examples && result.examples.length > 0) {
      exHtml = '<div class="examples">' +
        result.examples.map(e => `<div class="example-item">💡 ${e.ru}<br>　 ${e.zh}</div>`).join('') +
        '</div>';
    }
    area.innerHTML = `
      ${isCorrected ? `<div class="corrected-note">✏️ 语法已修正：</div>` : ''}
      <div class="word-display">${result.corrected}</div>
      ${isCorrected ? `<div style="font-size:0.85rem;color:var(--muted);text-decoration:line-through;margin-bottom:4px">原始：${result.original}</div>` : ''}
      <div class="chinese-display">${result.chinese}</div>
      ${exHtml}
      <div style="font-size:0.8rem;color:var(--success);margin-top:6px">✅ 已添加到句式库</div>
    `;
    input.value = '';
    input.focus();
  }

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
    container.innerHTML = '<div style="text-align:center;color:var(--muted);padding:40px">暂无单词，去「录入生词」添加吧</div>';
    return;
  }

  container.innerHTML = data.words.map(w => {
    let exHtml = '';
    if (w.examples && w.examples.length > 0) {
      exHtml = '<div class="item-examples">' +
        w.examples.map(e => `📖 ${e.ru}<br>　 ${e.zh}`).join('<br>') +
        '</div>';
    }
    return `
      <div class="list-item">
        <div class="item-head">
          <div>
            <div class="item-main">${w.russian}</div>
            <div class="item-translation">${w.chinese}</div>
          </div>
          <button class="btn-small" onclick="deleteWord(${w.id})">删除</button>
        </div>
        ${exHtml}
        <div class="item-stats">
          <span class="correct">✅ ${w.correct_count}</span>
          <span class="wrong">❌ ${w.wrong_count}</span>
        </div>
      </div>
    `;
  }).join('');
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
    container.innerHTML = '<div style="text-align:center;color:var(--muted);padding:40px">暂无句式，去「录入句式」添加吧</div>';
    return;
  }

  container.innerHTML = data.sentences.map(s => {
    const isCorrected = s.corrected !== s.original;
    let exHtml = '';
    if (s.examples && s.examples.length > 0) {
      exHtml = '<div class="item-examples">' +
        s.examples.map(e => `💡 ${e.ru}<br>　 ${e.zh}`).join('<br>') +
        '</div>';
    }
    return `
      <div class="list-item">
        <div class="item-head">
          <div>
            <div class="item-main">${s.corrected || s.original}</div>
            ${isCorrected ? `<div style="font-size:0.8rem;color:var(--muted)">原始：${s.original}</div>` : ''}
            <div class="item-translation">${s.chinese}</div>
          </div>
          <button class="btn-small" onclick="deleteSentence(${s.id})">删除</button>
        </div>
        ${exHtml}
        <div class="item-stats">
          <span class="correct">✅ ${s.correct_count}</span>
          <span class="wrong">❌ ${s.wrong_count}</span>
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
}

async function startReview() {
  document.getElementById('review-start').style.display = 'none';
  document.getElementById('review-question').style.display = 'block';
  await loadNextQuestion();
}

async function loadNextQuestion() {
  const data = await api('POST', '/api/review/start');
  if (data.done) {
    document.getElementById('review-question').innerHTML = `
      <div style="text-align:center;padding:40px;color:var(--muted)">
        <p style="font-size:1.2rem">🎉 暂无复习内容</p>
        <p>请先录入单词或句式</p>
      </div>
    `;
    return;
  }
  renderQuestion(data.question);
}

function renderQuestion(q) {
  reviewQuestion = q;
  document.getElementById('question-label').textContent = q.question_label;
  document.getElementById('question-text').textContent = q.question;

  const container = document.getElementById('options-container');
  const labels = ['A', 'B', 'C'];
  container.innerHTML = q.options.map((opt, i) => `
    <button class="option-btn" data-index="${i}" onclick="submitAnswer(${i})">
      ${labels[i]}. ${opt}
    </button>
  `).join('');

  document.getElementById('review-feedback').innerHTML = '';
  document.getElementById('review-question').style.display = 'block';
}

async function submitAnswer(chosen) {
  if (!reviewQuestion) return;

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

  // 1.5 秒后加载下一题
  setTimeout(() => {
    if (result.done) {
      document.getElementById('review-question').innerHTML = `
        <div style="text-align:center;padding:40px">
          <p style="font-size:1.3rem">🎉 复习完成！</p>
          <button class="btn-primary" onclick="startReview()" style="margin-top:20px">再来一轮</button>
        </div>
      `;
    } else if (result.next_question) {
      renderQuestion(result.next_question);
    } else {
      document.getElementById('review-question').innerHTML = `
        <div style="text-align:center;padding:40px;color:var(--muted)">
          <p style="font-size:1.2rem">🎉 暂无更多复习内容</p>
          <button class="btn-primary" onclick="startReview()" style="margin-top:20px">再来一轮</button>
        </div>
      `;
    }
  }, 1500);
}
