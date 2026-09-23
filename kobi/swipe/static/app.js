'use strict';
/* kobi swipe — one card per instrument; space cycles through its versions (the bank's sound, then the
   same instrument from other banks and libraries); a swipe gives the instrument its verdict.  Web Audio
   keeps a version and its compare variants in sync, so switching never loses the place in the phrase. */

const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const store = {
  get(k, d) { try { const v = localStorage.getItem('swipe.' + k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem('swipe.' + k, JSON.stringify(v)); } catch { /* private mode */ } },
};
const sleep = ms => new Promise(r => setTimeout(r, ms));

const FAMILIES = ['Piano', 'Chromatic percussion', 'Organ', 'Guitar', 'Bass', 'Strings', 'Ensemble', 'Brass', 'Reed', 'Pipe',
  'Synth lead', 'Synth pad', 'Synth effects', 'Ethnic', 'Percussive', 'Sound effects', 'Drum kit'];
const hueOf = fam => Math.round((Math.max(0, FAMILIES.indexOf(fam)) * 360 / FAMILIES.length + 330) % 360);
const fmtMB = b => (b >= 1e9 ? (b / 1e9).toFixed(2) + ' GB' : b >= 1e6 ? (b / 1e6).toFixed(1) + ' MB' : Math.round(b / 1e3) + ' KB');
const num = p => (p === 128 ? 'KIT' : String(p).padStart(3, '0'));

let ctx = null;                 // AudioContext, made inside the first gesture
const buffers = new Map();      // media key -> Promise<AudioBuffer>
let card = null;                // the instrument on screen, with all its versions
let focus = null;               // id of the version on screen ('bank' or an alternative)
let wantFocus = null;           // the version to land on when the next card arrives (after back)
let enterFrom = null;           // 'left' when back brought a card in
let cardEl = null;
let player = null;              // { t0, dur, id, nodes: {variant: {src, g}} }
let variant = 'main';           // which compare variant of the version is audible
let autoplayWhenReady = null;   // a version the viewer moved to before it was ready
let busy = false;
let pollTimer = null;
let format = store.get('format', 'mp3');
let autoplay = store.get('autoplay', true);

// ------------------------------------------------------------------ server
async function api(path, body) {
  const r = await fetch(path, body ? { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) } : {});
  if (!r.ok) throw new Error((await r.json().catch(() => ({}))).error || r.statusText);
  return r.json();
}

function load(key) {
  if (!buffers.has(key)) {
    const p = fetch(`/media/${key}.${format}`).then(r => { if (!r.ok) throw new Error('audio ' + r.status); return r.arrayBuffer(); })
      .then(b => ctx.decodeAudioData(b));
    p.catch(() => buffers.delete(key));
    buffers.set(key, p);
    if (buffers.size > 60) buffers.delete(buffers.keys().next().value);
  }
  return buffers.get(key);
}

// ------------------------------------------------------------------ versions and their compare variants
const playable = () => (card ? card.options.filter(o => o.audio.status !== 'failed') : []);
const current = () => (card ? card.options.find(o => o.id === focus) : null);

function variantsOf(o) {
  if (!o) return [];
  if (o.type === 'bank') {
    const v = [{ id: 'main', label: 'Slim bank', a: o.audio }, { id: 'micro', label: 'Microscopic', a: o.compare.micro }];
    if (o.compare.source) v.push({ id: 'source', label: 'Source (raw)', a: o.compare.source });
    return v;
  }
  return [{ id: 'main', label: 'This one', a: o.audio }, { id: 'bank', label: 'Bank now', a: card.options[0].audio }];
}
const compareTarget = o => (o && o.type === 'alt' ? 'bank' : 'source');

// ------------------------------------------------------------------ playback
function stop() {
  if (player) {
    for (const n of Object.values(player.nodes)) { try { n.src.stop(); } catch { /* already stopped */ } }
    player = null;
  }
  const t = cardEl && cardEl.querySelector('.playtoggle');
  if (t) t.classList.remove('playing');
}

async function play(from = 0) {
  const o = current();
  if (!o || !ctx) return;
  const vs = variantsOf(o).filter(v => v.a && v.a.status === 'done');
  if (!vs.some(v => v.id === 'main')) return;
  let bufs;
  try { bufs = await Promise.all(vs.map(v => load(v.a.key))); } catch (e) { note('audio failed to load: ' + e.message); return; }
  if (!current() || current().id !== o.id) return;              // moved on while it loaded (polls replace the objects)
  stop();
  if (!vs.some(v => v.id === variant)) variant = 'main';
  const dur = Math.max(...bufs.map(b => b.duration));
  from = from >= dur - 0.05 || !(from > 0) ? 0 : from;          // a switch right after a start reads slightly negative
  const t = ctx.currentTime + 0.03;
  const p = { t0: t - from, dur, id: o.id, nodes: {} };
  vs.forEach((v, i) => {
    const src = ctx.createBufferSource();
    src.buffer = bufs[i];
    const g = ctx.createGain();
    g.gain.value = v.id === variant ? 1 : 0;
    src.connect(g).connect(ctx.destination);
    src.start(t, Math.min(from, bufs[i].duration - 0.01));
    p.nodes[v.id] = { src, g };
  });
  player = p;
  const tg = cardEl.querySelector('.playtoggle');
  if (tg) tg.classList.add('playing');
  const tick = () => {
    if (player !== p) return;
    const pos = ctx.currentTime - p.t0;
    drawWave(pos / p.dur);
    if (pos >= p.dur) { stop(); drawWave(0); return; }
    requestAnimationFrame(tick);
  };
  requestAnimationFrame(tick);
}

function setVariant(id) {
  const v = variantsOf(current()).find(x => x.id === id);
  if (!v || !v.a || v.a.status !== 'done') return;
  variant = id;
  if (player) {
    for (const [k, n] of Object.entries(player.nodes)) n.g.gain.setTargetAtTime(k === id ? 1 : 0, ctx.currentTime, 0.012);
    if (!player.nodes[id]) play(ctx.currentTime - player.t0);
  }
  if (cardEl) cardEl.querySelectorAll('.variants button').forEach(b => b.classList.toggle('on', b.dataset.v === id));
  drawWave(player ? (ctx.currentTime - player.t0) / player.dur : 0);
}

// the next (dir 1) or previous (-1) version of the instrument; playing carries on at the same place
function cycle(dir) {
  const list = playable();
  if (!list.length || busy) return;
  commitNote();
  let i = list.findIndex(o => o.id === focus);
  if (i < 0) i = 0;
  setFocus(list[(i + dir + list.length) % list.length].id);
}

function setFocus(id) {
  commitNote();
  const pos = player ? Math.max(0, ctx.currentTime - player.t0) : 0;
  const wasPlaying = !!player;
  focus = id;
  variant = 'main';
  renderOption();
  const o = current();
  if (o && o.audio.status === 'done') {
    autoplayWhenReady = null;
    play(wasPlaying ? pos : 0);
  } else {
    stop();
    autoplayWhenReady = id;
  }
  refresh();                                                     // the server prepares this one and the next
}

// ------------------------------------------------------------------ drawing
function drawWave(frac) {
  const cv = cardEl && cardEl.querySelector('canvas');
  if (!cv) return;
  const vs = variantsOf(current());
  const v = vs.find(x => x.id === variant) || vs[0];
  const wave = v && v.a && v.a.wave;
  const dpr = window.devicePixelRatio || 1;
  const w = cv.clientWidth, h = cv.clientHeight;
  if (cv.width !== Math.round(w * dpr) || cv.height !== Math.round(h * dpr)) { cv.width = Math.round(w * dpr); cv.height = Math.round(h * dpr); }
  const g = cv.getContext('2d');
  g.setTransform(dpr, 0, 0, dpr, 0, 0);
  g.clearRect(0, 0, w, h);
  if (!wave) return;
  const cs = getComputedStyle(document.documentElement);
  const on = cs.getPropertyValue('--wave-on').trim(), off = cs.getPropertyValue('--wave').trim();
  const n = wave.length, bw = w / n, peak = Math.max(0.05, ...wave);
  for (let i = 0; i < n; i++) {
    const a = Math.max(1.5, (wave[i] / peak) * (h * 0.46));
    g.fillStyle = i / n < frac ? on : off;
    g.fillRect(i * bw + bw * 0.18, h / 2 - a, Math.max(1, bw * 0.64), a * 2);
  }
}

function renderCard() {
  const stack = $('#stack');
  stop();
  stack.innerHTML = '<div class="card behind"></div>';
  cardEl = document.createElement('div');
  if (!card) {
    cardEl.className = 'card empty';
    cardEl.innerHTML = `<h2>All rated</h2><p>Every instrument has a verdict. Open the list to change one.</p>
      <p><button class="ghost" data-act="list">Open the list</button></p>`;
    cardEl.querySelector('[data-act=list]').addEventListener('click', openList);
    stack.appendChild(cardEl);
    setButtons();
    return;
  }
  const hue = hueOf(card.family);
  cardEl.className = 'card';
  cardEl.style.cssText = `--hue: hsl(${hue} 62% 58%); --hue-ink: hsl(${hue} 55% 42%); --hue-ink-dark: hsl(${hue} 70% 74%)`;
  cardEl.innerHTML = `<div class="band"></div><div class="bars" role="group" aria-label="Versions"></div>
    <div class="meta"><span class="num">${num(card.program)}</span><span class="fam">${esc(card.family)}</span><span class="kind"></span></div>
    <h2>${esc(card.name)}</h2>
    ${card.review ? `<div class="review">${esc(reviewText(card.review))}</div>` : ''}
    <div class="option"><div class="t"></div><div class="l"></div><div class="notebox"></div></div>
    <div class="chips"></div>
    <div class="wave"><canvas></canvas><div class="busy" hidden></div></div>
    <div class="playrow">
      <button class="playtoggle" title="Replay (Enter)" aria-label="Play"><svg viewBox="0 0 24 24" class="i-play"><path d="M8 5v14l11-7z"/></svg><svg viewBox="0 0 24 24" class="i-stop"><path d="M7 7h10v10H7z"/></svg></button>
      <button class="notebtn" title="Note on this version (N)" aria-label="Note"><svg viewBox="0 0 24 24"><path d="M4 20h4L19 9l-4-4L4 16v4z"/><path d="M13.5 6.5l4 4"/></svg></button>
      <div class="variants" role="group" aria-label="Compare"></div>
    </div>
    <div class="stamp like">THIS ONE</div><div class="stamp nope">NONE</div>`;
  cardEl.querySelector('.playtoggle').addEventListener('click', () => (player ? stop() : play(0)));
  cardEl.querySelector('.notebtn').addEventListener('click', () => editNote());
  if (enterFrom === 'left') {
    cardEl.classList.add('enter-left');
    requestAnimationFrame(() => requestAnimationFrame(() => cardEl.classList.remove('enter-left')));
  }
  enterFrom = null;
  stack.appendChild(cardEl);
  bindDrag(cardEl);
  renderOption(true);
}

let shownSig = '';
function renderOption(force = false) {
  if (!card || !cardEl) return;
  const o = current();
  if (!o) return;
  const list = playable();
  const sig = JSON.stringify([focus, variant, card.options.map(x => [x.id, x.audio.status, x.audio.progress, x.audio.key, x.note])]);
  if (!force && sig === shownSig) return;
  shownSig = sig;
  // one bar per version
  const bars = cardEl.querySelector('.bars');
  bars.innerHTML = card.options.map(x => `<button data-id="${x.id}" title="${esc(x.type === 'bank' ? 'Now in the bank' : x.title + ' · ' + x.lib_title)}"
    class="${x.id === focus ? 'on' : ''} ${x.passed ? 'passed' : ''} ${x.new && card.review ? 'new' : ''} ${x.audio.status === 'failed' ? 'failed' : ''}"></button>`).join('');
  bars.querySelectorAll('button').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); setFocus(b.dataset.id); }));
  const pos = list.findIndex(x => x.id === focus);
  cardEl.querySelector('.kind').textContent = `version ${pos + 1} of ${list.length}`;
  cardEl.querySelector('.option .t').textContent = o.type === 'bank' ? 'Now in the bank' : o.title;
  cardEl.querySelector('.option .l').textContent = o.lib_title;
  if (!editing) renderNote(o);
  // chips
  const chips = [];
  if (o.type === 'bank') {
    if (card.standin) chips.push('<span class="chip warn">stand-in timbre</span>');
  } else {
    if (o.new && card.review) chips.push('<span class="chip new">new</span>');
    const lic = o.license || 'licence unknown';
    chips.push(`<span class="chip ${/cc0|public|unrestricted/i.test(lic) ? 'good' : /gpl|sampling|nc/i.test(lic) ? 'warn' : ''}">${esc(lic)}</span>`);
    chips.push(o.remote ? `<span class="chip">remote${o.audio.fetched ? ' · ' + fmtMB(o.audio.fetched) + ' fetched' : ''}</span>` : '<span class="chip">on disk</span>');
    if (o.remote && o.audio.full_bytes) chips.push(`<span class="chip ${o.audio.full_bytes > 100e6 ? 'warn' : ''}">whole instrument ${fmtMB(o.audio.full_bytes)}</span>`);
    if (o.listed) chips.push('<span class="chip">gm_map fallback</span>');
    if (o.audio.shift) chips.push(`<span class="chip warn">phrase ${o.audio.shift > 0 ? 'up' : 'down'} ${Math.abs(o.audio.shift / 12)} oct (range)</span>`);
  }
  if (o.passed) chips.push('<span class="chip">you passed on this before</span>');
  cardEl.querySelector('.chips').innerHTML = chips.join('');
  // preparing / failed
  const busyEl = cardEl.querySelector('.busy');
  const a = o.audio;
  if (a.status === 'done') {
    busyEl.hidden = true;
  } else {
    busyEl.hidden = false;
    busyEl.innerHTML = a.status === 'failed' ? `<span>Could not render: ${esc(a.error || 'failed')}</span>`
      : `<div class="spinner"></div><span>${esc(a.progress || (a.status === 'running' ? 'rendering' : 'preparing'))}</span>`;
  }
  // compare variants
  const vs = variantsOf(o);
  const vb = cardEl.querySelector('.variants');
  vb.innerHTML = vs.map(v => `<button data-v="${v.id}" class="${v.id === variant ? 'on' : ''}" ${v.a && v.a.status === 'done' ? '' : 'disabled'}>${esc(v.label)}${v.a && v.a.status !== 'done' && v.a.status !== 'failed' ? ' …' : ''}</button>`).join('');
  vb.querySelectorAll('button').forEach(b => b.addEventListener('click', e => { e.stopPropagation(); setVariant(b.dataset.v); }));
  const tg = cardEl.querySelector('.playtoggle');
  tg.disabled = a.status !== 'done';
  tg.classList.toggle('playing', !!player);
  drawWave(player ? (ctx.currentTime - player.t0) / player.dur : 0);
  setButtons();
}

function reviewText(r) {
  const had = r.decision === 'pick' ? `you picked ${r.pick}` : r.decision === 'keep' ? "you kept the bank's sound"
    : r.decision === 'none' ? 'none of them was right' : 'you skipped it';
  return `Another look · ${had}${r.reason ? ` · “${r.reason}”` : ''} · ${r.new} new version${r.new === 1 ? '' : 's'} first · ↓ keeps what you had`;
}

function setButtons() {
  const dis = !card || busy;
  $('#skipBtn').title = card && card.review ? 'Keep what I had (↓)' : 'Decide later (↓)';
  ['#noneBtn', '#skipBtn', '#nextBtn'].forEach(s => { $(s).disabled = dis; });
  $('#pickBtn').disabled = dis || !current() || current().audio.status !== 'done';
}

// ------------------------------------------------------------------ notes on a version
let editing = null;                                                // { program, option, el } while a note is being typed

function renderNote(o) {
  const box = cardEl && cardEl.querySelector('.notebox');
  if (!box) return;
  box.innerHTML = o.note ? `<button class="note" title="Edit the note (N)">${esc(o.note)}</button>` : '';
  const b = box.querySelector('.note');
  if (b) b.addEventListener('click', e => { e.stopPropagation(); editNote(); });
  const nb = cardEl.querySelector('.notebtn');
  if (nb) nb.classList.toggle('has', !!o.note);
}

function editNote() {
  const o = current();
  if (!card || !o || editing || busy) return;
  const box = cardEl.querySelector('.notebox');
  box.innerHTML = `<textarea class="noteedit" rows="2" maxlength="2000" placeholder="A note on this version: what it does well, what is off…"></textarea>
    <div class="notehint"><span>Enter saves · Shift+Enter new line · Esc cancels</span><button class="mini" data-save>Save</button></div>`;
  const ta = box.querySelector('textarea');
  ta.value = o.note || '';
  editing = { program: card.program, option: o.id, el: ta, before: o.note || '' };
  ta.addEventListener('keydown', e => {
    e.stopPropagation();                                           // space and arrows type, they do not swipe
    if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); commitNote(); }
    else if (e.key === 'Escape') { e.preventDefault(); cancelNote(); }
  });
  ta.addEventListener('pointerdown', e => e.stopPropagation());
  box.querySelector('[data-save]').addEventListener('click', e => { e.stopPropagation(); commitNote(); });
  ta.focus();
  ta.setSelectionRange(ta.value.length, ta.value.length);
}

function cancelNote() {
  if (!editing) return;
  editing = null;
  const o = current();
  if (o) renderNote(o);
}

async function commitNote() {
  if (!editing) return;
  const { program, option, el, before } = editing;
  const text = el.value.trim();
  editing = null;
  const o = card && card.program === program ? card.options.find(x => x.id === option) : null;
  if (o) { o.note = text; if (current() && current().id === option) renderNote(o); }
  if (text === before.trim()) return;
  try { await api('/api/note', { program, option, text }); note(text ? 'note saved' : 'note removed'); }
  catch (e) { note('note not saved: ' + e.message); }
}

// ------------------------------------------------------------------ talking to the deck
let asked = 0, applied = 0;                                        // fast cycling sends several requests at once
async function refresh() {
  clearTimeout(pollTimer);
  const mine = ++asked;
  let r;
  try {
    const f = focus || wantFocus;
    r = await api('/api/deck' + (f ? '?focus=' + encodeURIComponent(f) : ''));
  } catch (e) {
    note('server unreachable: ' + e.message);
    pollTimer = setTimeout(refresh, 3000);
    return;
  }
  if (mine < applied) return;                                     // an older answer overtaken by a newer one
  applied = mine;
  if (busy) return;                                               // a verdict is on its way: its own refresh follows
  status(r.status);
  const c = r.card;
  const fresh = !c || !card || c.program !== card.program;
  card = c;
  if (fresh) {
    focus = c ? c.focus : null;
    wantFocus = null;
    variant = 'main';
    autoplayWhenReady = focus;
    shownSig = '';
    renderCard();
  } else {
    if (!card.options.some(o => o.id === focus)) focus = card.focus;
    renderOption();
  }
  const o = current();
  if (o && o.audio.status === 'failed' && playable().length) {     // a version that cannot play: move past it
    cycle(1);
    return;
  }
  if (o && o.audio.status === 'done' && autoplayWhenReady === focus) {
    autoplayWhenReady = null;
    if (autoplay && ctx) play(0);
  }
  // warm the neighbours' audio
  if (ctx && card) {
    const list = playable(), i = list.findIndex(x => x.id === focus);
    for (const d of [1, -1, 2]) {
      const n = list[(i + d + list.length) % list.length];
      if (n && n.audio.status === 'done') load(n.audio.key).catch(() => {});
    }
    for (const n of r.next || []) if (n.bank.status === 'done') load(n.bank.key).catch(() => {});
  }
  const pending = card && [current(), ...playable().slice(0, 3)].some(x => x && (x.audio.status === 'queued' || x.audio.status === 'running'));
  pollTimer = setTimeout(refresh, pending ? 1000 : 5000);
}

function status(s) {
  $('#tally').textContent = `${s.voted}/${s.total} · ${s.picks} replaced${s.none ? ` · ${s.none} none` : ''}${s.review ? ` · ${s.review} to review` : ''}`;
  const f = s.fetch, bits = [`${fmtMB(f.total)} fetched this session`];
  if (f.current) bits.push(`${f.current.label}${f.current.size ? ` ${Math.round(100 * f.current.done / f.current.size)}%` : ''}`);
  const run = (s.jobs.running || []).filter(j => j.progress).map(j => j.progress);
  if (run.length) bits.push(run[0]);
  const cat = s.catalog;
  if (cat.remote_indexed + Object.keys(cat.remote_errors).length < cat.remote_total) bits.push(`indexing remote libraries ${cat.remote_indexed}/${cat.remote_total}`);
  $('#net').textContent = bits.join(' · ');
}

function note(msg) { $('#net').textContent = msg; }

// ------------------------------------------------------------------ verdicts
async function decide(verdict) {                                    // 'pick' | 'none' | 'skip'
  if (!card || busy) return;
  await commitNote();
  if (verdict === 'pick' && (!current() || current().audio.status !== 'done')) return;
  busy = true;
  clearTimeout(pollTimer);
  setButtons();
  stop();
  const program = card.program, option = focus;
  if (cardEl) {
    cardEl.classList.remove('dragging');
    cardEl.style.transform = '';
    cardEl.classList.add(verdict === 'pick' ? 'gone-right' : verdict === 'none' ? 'gone-left' : 'gone-down');
  }
  try { await api('/api/vote', { program, verdict, option }); } catch (e) { note('vote failed: ' + e.message); }
  await sleep(200);
  card = null; focus = null; busy = false;
  await refresh();
}

async function back() {
  if (busy) return;
  await commitNote();
  busy = true;
  clearTimeout(pollTimer);
  stop();
  try {
    const r = await api('/api/back', {});
    if (r.program === null) note('nothing to go back to');
    else { wantFocus = r.focus; enterFrom = 'left'; }
  } catch (e) { note('back failed: ' + e.message); }
  card = null; focus = null; busy = false;
  await refresh();
}

// ------------------------------------------------------------------ gestures
function bindDrag(el) {
  let s = null;
  el.addEventListener('pointerdown', e => {
    if (e.button !== 0 || e.target.closest('button, textarea') || busy) return;
    s = { x: e.clientX, y: e.clientY, id: e.pointerId, moved: false };
    el.setPointerCapture(e.pointerId);
    el.classList.add('dragging');
  });
  el.addEventListener('pointermove', e => {
    if (!s || e.pointerId !== s.id) return;
    const dx = e.clientX - s.x, dy = e.clientY - s.y;
    if (Math.abs(dx) + Math.abs(dy) > 8) s.moved = true;
    if (!s.moved) return;
    el.style.transform = `translate(${dx}px, ${Math.max(0, dy) * 0.35}px) rotate(${dx / 18}deg)`;
    const like = el.querySelector('.stamp.like'), nope = el.querySelector('.stamp.nope');
    if (like) like.style.opacity = Math.max(0, Math.min(1, dx / 110));
    if (nope) nope.style.opacity = Math.max(0, Math.min(1, -dx / 110));
  });
  const end = e => {
    if (!s || e.pointerId !== s.id) return;
    const dx = e.clientX - s.x, dy = e.clientY - s.y, moved = s.moved;
    s = null;
    el.classList.remove('dragging');
    if (!moved) {                                                   // a tap: the next version (left third: the previous)
      el.style.transform = '';
      const r = el.getBoundingClientRect();
      if (e.type === 'pointerup') cycle(e.clientX < r.left + r.width / 3 ? -1 : 1);
      return;
    }
    if (dx > 110) return decide('pick');
    if (dx < -110) return decide('none');
    if (dy > 150 && Math.abs(dx) < 80) return decide('skip');
    el.style.transform = '';
    el.querySelectorAll('.stamp').forEach(x => { x.style.opacity = 0; });
  };
  el.addEventListener('pointerup', end);
  el.addEventListener('pointercancel', end);
}

let held = null;
document.addEventListener('keydown', e => {
  if ($('#list').open || !$('#gate').classList.contains('hidden') || e.target.closest('input, textarea') ||
      e.metaKey || e.ctrlKey || e.altKey) return;
  if (e.key === ' ') { e.preventDefault(); cycle(e.shiftKey ? -1 : 1); }
  else if (e.key === 'ArrowRight') { e.preventDefault(); decide('pick'); }
  else if (e.key === 'ArrowLeft') { e.preventDefault(); decide('none'); }
  else if (e.key === 'ArrowDown') { e.preventDefault(); decide('skip'); }
  else if (e.key === 'ArrowUp' || e.key === 'Backspace') { e.preventDefault(); back(); }
  else if (e.key === 'Enter') { e.preventDefault(); play(0); }
  else if ((e.key === 'c' || e.key === 'C') && !e.repeat) { held = variant; setVariant(compareTarget(current())); }
  else if (/^[1-3]$/.test(e.key)) { const v = variantsOf(current())[+e.key - 1]; if (v) setVariant(v.id); }
  else if (e.key === 'l') { openList(); }
  else if (e.key === 'n' || e.key === 'N') { e.preventDefault(); editNote(); }
});
document.addEventListener('keyup', e => {
  if ((e.key === 'c' || e.key === 'C') && held) { setVariant(held); held = null; }
});

$('#noneBtn').addEventListener('click', () => decide('none'));
$('#pickBtn').addEventListener('click', () => decide('pick'));
$('#skipBtn').addEventListener('click', () => decide('skip'));
$('#nextBtn').addEventListener('click', () => cycle(1));
$('#backBtn').addEventListener('click', back);
window.addEventListener('resize', () => drawWave(0));

$('#startBtn').addEventListener('click', async () => {
  ctx = new (window.AudioContext || window.webkitAudioContext)();
  await ctx.resume();
  $('#gate').classList.add('hidden');
  await refresh();
});

// ------------------------------------------------------------------ the list
let listFilter = 'all';
let listPlayer = null;
const LABEL = { pick: 'replace', keep: 'keep', none: 'none', skip: 'skipped' };

async function openList() {
  const d = $('#list');
  if (!d.open) d.showModal();
  stop();
  let ov;
  try { ov = await api('/api/overview'); } catch (e) { note('list failed: ' + e.message); return; }
  const tb = $('#listTable tbody');
  const rows = ov.rows.filter(r => listFilter === 'all' || (listFilter === 'picked' && r.decision === 'pick') ||
    (listFilter === 'kept' && r.decision === 'keep') || (listFilter === 'none' && r.decision === 'none') ||
    (listFilter === 'skipped' && r.decision === 'skip') || (listFilter === 'open' && !r.decision));
  tb.innerHTML = rows.map(r => {
    const v = r.decision === 'pick' ? 'replace' : r.decision === 'keep' ? 'keep' : r.decision === 'none' ? 'searching' : '';
    const label = (LABEL[r.decision] || '—') + (r.review ? ' · review' : '');
    const state = r.full === 'running' ? ' · ' + esc(r.full_progress || 'fetching') : r.full === 'done' ? ' · on disk'
      : r.full === 'queued' ? ' · fetch queued' : '';
    const pick = (r.pick ? `<div>${esc(r.pick.title)}</div><div class="sub">${esc(r.pick.lib_title)} · ${esc(r.pick.license)}${state}</div>` : '')
      + `<div class="listnote" data-program="${r.program}" data-option="${esc(r.note_on)}">${r.note ? `<span class="note">${esc(r.note)}</span>` : ''}</div>`;
    const noteBtn = `<button class="mini" data-note="${r.program}">${r.note ? 'edit note' : 'note'}</button>`;
    const fetchBtn = r.pick && r.full === 'confirm' ? `<button class="mini" data-fetch="${r.pick.cid}">fetch whole instrument${r.full_bytes ? ' (' + fmtMB(r.full_bytes) + ')' : ''}</button>` : '';
    const bank = r.bank_audio && r.bank_audio.status === 'done' ? `<button class="mini" data-play="${r.bank_audio.key}">▶ bank</button>` : '';
    const pk = r.pick_audio && r.pick_audio.status === 'done' ? `<button class="mini" data-play="${r.pick_audio.key}">▶ pick</button>` : '';
    const act = r.decision ? `<button class="mini" data-reopen="${r.program}">change</button>` : `<button class="mini" data-go="${r.program}">go</button>`;
    return `<tr><td class="n">${num(r.program)}</td>
      <td><div>${esc(r.name)}</div><div class="sub">${esc(r.family)}</div></td>
      <td class="v"><span class="verdict ${v}">${label}</span></td><td class="pk">${pick}</td><td class="act">${bank}${pk}${fetchBtn}${noteBtn}${act}</td></tr>`;
  }).join('') + `<tr><td colspan="5" class="sub wide">Audio: <button class="mini" data-fmt="mp3">${format === 'mp3' ? '● ' : ''}MP3</button>
      <button class="mini" data-fmt="flac">${format === 'flac' ? '● ' : ''}FLAC (lossless)</button>
      &nbsp; Autoplay: <button class="mini" data-auto="1">${autoplay ? 'on' : 'off'}</button>
      &nbsp; Picks are written to SWIPE_PICKS.md in the repository.</td></tr>`;
  tb.querySelectorAll('[data-play]').forEach(b => b.addEventListener('click', async () => {
    if (listPlayer) { try { listPlayer.stop(); } catch { } listPlayer = null; }
    if (!ctx) return;
    const buf = await load(b.dataset.play);
    listPlayer = ctx.createBufferSource(); listPlayer.buffer = buf; listPlayer.connect(ctx.destination); listPlayer.start();
  }));
  const reload = async () => { d.close(); card = null; focus = null; await refresh(); };
  tb.querySelectorAll('[data-reopen]').forEach(b => b.addEventListener('click', async () => {
    await api('/api/reopen', { program: +b.dataset.reopen }); await reload();
  }));
  tb.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', async () => {
    await api('/api/cursor', { program: +b.dataset.go }); await reload();
  }));
  tb.querySelectorAll('[data-note]').forEach(b => b.addEventListener('click', () => {
    const cell = tb.querySelector(`.listnote[data-program="${b.dataset.note}"]`);
    if (!cell || cell.querySelector('textarea')) return;
    const old = cell.querySelector('.note') ? cell.querySelector('.note').textContent : '';
    cell.innerHTML = `<textarea class="noteedit" rows="2" maxlength="2000" placeholder="A note on ${cell.dataset.option === 'bank' ? 'the bank\'s sound' : 'this pick'}…"></textarea>
      <div class="notehint"><span>Enter saves · Esc cancels</span></div>`;
    const ta = cell.querySelector('textarea');
    ta.value = old;
    ta.focus();
    ta.addEventListener('keydown', async e => {
      e.stopPropagation();
      if (e.key === 'Escape') { e.preventDefault(); openList(); }
      else if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        try { await api('/api/note', { program: +cell.dataset.program, option: cell.dataset.option, text: ta.value }); }
        catch (err) { note('note not saved: ' + err.message); }
        openList();
      }
    });
  }));
  tb.querySelectorAll('[data-fetch]').forEach(b => b.addEventListener('click', async () => {
    await api('/api/fetch', { cid: b.dataset.fetch }); openList();
  }));
  tb.querySelectorAll('[data-fmt]').forEach(b => b.addEventListener('click', () => {
    format = b.dataset.fmt; store.set('format', format); buffers.clear(); openList();
  }));
  tb.querySelectorAll('[data-auto]').forEach(b => b.addEventListener('click', () => {
    autoplay = !autoplay; store.set('autoplay', autoplay); openList();
  }));
}
$('#listBtn').addEventListener('click', openList);
$('#closeList').addEventListener('click', () => $('#list').close());
$('#list').addEventListener('close', () => { if (listPlayer) { try { listPlayer.stop(); } catch { } listPlayer = null; } });
document.querySelectorAll('.filters button').forEach(b => b.addEventListener('click', () => {
  listFilter = b.dataset.f;
  document.querySelectorAll('.filters button').forEach(x => x.classList.toggle('on', x === b));
  openList();
}));
