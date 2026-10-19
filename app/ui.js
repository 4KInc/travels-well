/* Components every view shares. Kept here so a table or a tab strip cannot
   drift into looking different on one page than another. */
const el = (t, c, x) => { const e = document.createElement(t);
  if (c) e.className = c; if (x !== undefined) e.textContent = x; return e; };
const svgEl = (t, a) => { const e = document.createElementNS('http://www.w3.org/2000/svg', t);
  for (const k in a) e.setAttribute(k, a[k]); return e; };
const fmt = v => (v >= 0 ? '+' : '−') + Math.abs(v).toFixed(2);

function gallery(items, dim) {
  const g = el('div', 'gal' + (dim ? ' dim' : ''));
  (items || []).forEach(f => {
    const fig = el('figure');
    const ph = el('div', 'noart');
    fig.appendChild(ph);
    if (f.image) {
      const im = new Image(); im.src = f.image; im.alt = ''; im.loading = 'lazy';
      im.onload = () => ph.remove();
      im.onerror = () => im.remove();
      fig.appendChild(im);
    }
    fig.appendChild(el('figcaption', null, f.title));
    g.appendChild(fig);
  });
  return g;
}

/* One table for every signed movement in the application: poster, title,
   direction, a bar centred on zero, the number. */
function shiftTable(rows, label) {
  const t = el('table');
  t.innerHTML = '<thead><tr><th style="width:40px"></th><th>Film</th>' +
    '<th style="width:100px">Direction</th><th style="width:120px">Shift</th>' +
    '<th class="n" style="width:64px">' + (label || 'vs home') + '</th></tr></thead>';
  const tb = el('tbody');
  const peak = Math.max(...rows.map(r => Math.abs(r.shift)), 0.01);
  rows.forEach(r => {
    const tr = el('tr');
    const td0 = el('td');
    if (r.image) {
      const im = new Image(); im.className = 'poster'; im.src = r.image;
      im.alt = ''; im.loading = 'lazy';
      im.onerror = () => im.remove();
      td0.appendChild(im);
    }
    tr.appendChild(td0);
    tr.appendChild(el('td', 'ttl', r.title));
    tr.appendChild(el('td', null, r.shift >= 0 ? 'Travels' : 'Stays behind'));
    const cell = el('td'), m = el('div', 'mini'), i = el('i');
    i.style.width = Math.round(Math.abs(r.shift) / peak * 50) + '%';
    if (r.shift >= 0) { i.style.left = '50%'; }
    else { i.style.right = '50%'; i.style.background = 'var(--bad)'; }
    m.appendChild(i); cell.appendChild(m); tr.appendChild(cell);
    tr.appendChild(el('td', 'n num ' + (r.shift >= 0 ? 'up' : 'down'), fmt(r.shift)));
    tb.appendChild(tr);
  });
  t.appendChild(tb);
  return t;
}

/* Tab strip + pane. Panes build lazily, so a heavy tab costs nothing until
   it is opened. Returns the index it settled on. */
function mountTabs(tabbar, panes, tabs, want) {
  let at = (want != null && want < tabs.length) ? want : 0;
  tabbar.innerHTML = '';
  const paint = () => {
    [...tabbar.children].forEach((b, i) => b.setAttribute('aria-selected', String(i === at)));
    panes.innerHTML = ''; panes.appendChild(tabs[at].build());
  };
  tabs.forEach((t, i) => {
    const b = el('button');
    b.appendChild(document.createTextNode(t.name));
    if (t.n != null) b.appendChild(el('span', 'n', t.n));
    b.onclick = () => { at = i; paint(); if (t.onpick) t.onpick(i); };
    tabbar.appendChild(b);
  });
  paint();
  return at;
}

function traceList(steps) {
  const ol = el('ol', 'steps');
  (steps || []).forEach(s => {
    const li = el('li');
    const who = el('div', 'who' + (s.actor ? ' ' + s.actor : ''), s.actor || 'agent');
    const body = el('div');
    body.appendChild(el('div', 'act', (s.action || '').replace(/_/g, ' ')));
    if (s.reason) body.appendChild(el('div', 'why', s.reason));
    if (s.observed) body.appendChild(el('div', 'obs', s.observed));
    if (s.did) body.appendChild(el('div', 'did', s.did));
    if (s.rejected && s.rejected.length)
      body.appendChild(el('div', 'obs', 'passed over: ' + s.rejected.join(', ')));
    li.appendChild(who); li.appendChild(body);
    ol.appendChild(li);
  });
  return ol;
}
