const $ = id => document.getElementById(id);
const data = JSON.parse($('pilotData').textContent);
const {cards: words, evidence, manifest, stats} = data;
const sources = new Map(manifest.sources.map(source => [source.id, source]));
const audio = $('audio'), card = $('card'), list = $('list');
const speechEnds = words.map(word => word.audio.spokenEnd);
const KEY = 'oxford3000-ielts-semantic-pilot-position';
const parts = {'n.': '名词', 'v.': '动词', 'adj.': '形容词', 'adv.': '副词短语'};
let current = 0, lastSaved = -1, pendingSeek = null, interacted = false, showChinese = false;

const escapeHtml = value => String(value).replace(/[&<>"']/g, character => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[character]);

function saved() {
  try { return Number(localStorage.getItem(KEY) || 0); } catch { return 0; }
}

function savePosition() {
  if (!interacted) return;
  try { localStorage.setItem(KEY, String(audio.currentTime)); } catch {}
}

function citation(ident) {
  const row = evidence[ident];
  const source = sources.get(row.source);
  const firstPage = row.lines[0][0];
  const lastPage = row.lines[row.lines.length - 1][0];
  const pages = firstPage === lastPage ? firstPage : `${firstPage}–${lastPage}`;
  const location = row.lines.map(([page, first, last]) => `第 ${page} 页提取行 ${first}–${last}`).join('；');
  return `<a href="来源/${escapeHtml(source.file)}#page=${firstPage}" target="_blank" rel="noopener"
            title="${escapeHtml(location)}">${escapeHtml(source.title)} · PDF 第 ${pages} 页</a>
          <span class="muted">${escapeHtml(row.sentence)} · 词形 ${escapeHtml(row.form)}</span>`;
}

function evidenceList(ids) {
  return `<ul class="evidence">${ids.map(id => `<li>${citation(id)}${evidence[id].reason
    ? ` · ${escapeHtml(evidence[id].reason)}` : ''}</li>`).join('')}</ul>`;
}

function renderCollocation(item) {
  const forms = item.forms.length > 1
    ? `<span class="forms muted">原文形式 ${item.forms.map(escapeHtml).join(' / ')}</span>` : '';
  return `<li><details>
    <summary><span class="collocation-text">${escapeHtml(item.text)}</span><span class="pill">${item.count} 次</span></summary>
    ${forms}${evidenceList(item.evidence)}
  </details></li>`;
}

function renderExample(example) {
  if (!example) return '<p class="muted">暂未核实首位搭配的完整原句。</p>';
  const {text, start, end} = example;
  return `<figure class="example">
    <blockquote>${escapeHtml(text.slice(0, start))}<mark>${escapeHtml(text.slice(start, end))}</mark>${escapeHtml(text.slice(end))}</blockquote>
    <figcaption class="muted">官方样题 · ${citation(example.evidence)} · © IELTS Partners</figcaption>
  </figure>`;
}

function renderSense(sense, index, open) {
  const label = sense.construction || `义项 ${index + 1}`;
  const collocations = sense.collocations.length
    ? `<ul class="collocations">${sense.collocations.map(renderCollocation).join('')}</ul>`
    : '<p class="muted">暂未核实本义项的搭配。</p>';
  return `<details class="sense" data-sense="${escapeHtml(sense.id)}"${open ? ' open' : ''}>
    <summary><span class="sense-title">${escapeHtml(label)}</span>
      <span class="pill">${sense.count} 次</span>
      <span class="translation-text">${escapeHtml(sense.zh)}</span></summary>
    <div class="sense-content">
      <h4>样题搭配</h4>
      ${collocations}
      <h4>首位搭配的原句</h4>
      ${renderExample(sense.example)}
      <details class="muted">
        <summary>义项编号与全部出处</summary>
        <p>WordNet 3.0 · <code>${escapeHtml(sense.wordnetKey)}</code></p>
        ${evidenceList(sense.evidence)}
      </details>
    </div>
  </details>`;
}

function markCurrentEntry() {
  for (const button of list.querySelectorAll('.entry')) {
    const active = Number(button.dataset.index) === current;
    button.classList.toggle('current', active);
    if (active) button.setAttribute('aria-current', 'true');
    else button.removeAttribute('aria-current');
  }
}

function renderCard() {
  const word = words[current];
  const groups = word.groups.map((group, position) => `<section class="pos-group">
    <h3 class="pos-heading">${escapeHtml(group.pos)} ${escapeHtml(parts[group.pos])}
      <span class="muted">${group.count} 次 · ${group.senses.length} 个义项</span></h3>
    ${group.senses.map((sense, i) => renderSense(sense, i, position === 0 && i === 0)).join('')}
  </section>`);
  const originalUrl = $('original').getAttribute('href');
  const originalLinks = word.originals.map(entry => {
    const recordings = word.audio.sourceEntryIds.includes(entry.id) ? '（试听轨使用）' : '';
    return `<a href="${escapeHtml(originalUrl)}#word-${entry.id}" target="_blank" rel="noopener">
      ${escapeHtml(entry.level)} #${entry.id} · ${escapeHtml(entry.pos)}</a>${recordings}`;
  }).join(' · ');
  const uncounted = word.uncounted.length ? `<details class="muted">
    <summary>未计入的命中 · ${word.uncounted.length} 处</summary>${evidenceList(word.uncounted)}
    </details>` : '';
  card.innerHTML = `${StudyTranslations.toggle}
    <p class="eyebrow">WORD ${String(word.id).padStart(2, '0')} / ${words.length}</p>
    <h2 class="word-heading">${escapeHtml(word.word)}</h2>
    <div class="meta"><span class="pill">已核实 ${word.count} 次</span>
      <span>原文词形 ${word.forms.map(escapeHtml).join(' / ')}</span></div>
    ${groups.join('')}
    <div class="footnote muted">
      <p>原序词条与发音 ${originalLinks}</p>
      ${word.unseenPos.length ? `<p>本批样题未证实的 Oxford 词性 ${word.unseenPos.map(escapeHtml).join(' / ')}</p>` : ''}
      ${uncounted}
    </div>`;
  card.querySelector('.translation-toggle input').checked = showChinese;
  $('prevWord').disabled = current === 0;
  $('nextWord').disabled = current === words.length - 1;
  markCurrentEntry();
}

function renderList() {
  const query = $('search').value.trim().toLowerCase();
  const matches = words.filter(word => [word.word, ...word.forms].some(form => form.includes(query)));
  list.innerHTML = matches.map(word =>
    `<button class="entry" data-index="${word.id - 1}">${escapeHtml(word.word)}</button>`).join('');
  $('resultCount').textContent = `${matches.length} / ${words.length} 个词头`;
  markCurrentEntry();
}

function fromHash() {
  const match = location.hash.match(/^#word-([0-9]+)$/);
  if (match && Number(match[1]) >= 1 && Number(match[1]) <= words.length) {
    jump(Number(match[1]) - 1, false, false);
  }
}

function initialize() {
  const listening = manifest.sources.filter(source => source.section === 'listening').length;
  $('scope').textContent = `统计基于 ${listening} 段官方听力稿和 ${manifest.sources.length - listening} 篇学术阅读节选，共 ${stats.sentences} 个句段。频次仅代表这批材料。真人音轨按本页词序连续播放。`;
  $('credit').textContent = manifest.credit;
  $('officialIndex').href = manifest.index;
  $('officialTerms').href = manifest.terms;
  $('sourceLinks').innerHTML = manifest.sources.map(source => {
    const page = source.regions[0][0];
    const label = source.section === 'listening' ? '听力' : '学术阅读';
    return `<li>${escapeHtml(source.id)} · ${label} · ${escapeHtml(source.title)}
      <a href="来源/${escapeHtml(source.file)}#page=${page}" target="_blank" rel="noopener">本地 PDF</a> ·
      <a href="${escapeHtml(manifest.pdfs[source.file].url)}#page=${page}" target="_blank" rel="noopener">官方 PDF</a></li>`;
  }).join('');
  card.addEventListener('change', event => {
    if (event.target.matches('.translation-toggle input')) showChinese = event.target.checked;
  });
  list.addEventListener('click', event => {
    if (event.target.closest('.entry') && matchMedia('(max-width: 700px)').matches) window.scrollTo(0, 0);
  });
  $('search').addEventListener('input', renderList);
  window.addEventListener('hashchange', fromHash);
  window.addEventListener('pagehide', savePosition);
  renderCard();
  renderList();
  fromHash();
}
