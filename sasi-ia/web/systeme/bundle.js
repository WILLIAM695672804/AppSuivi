/* @ds-bundle: {"format":4,"namespace":"SASI","components":[{"name":"Button"},{"name":"LevelBadge"},{"name":"AlertCard"},{"name":"DataTable"},{"name":"TemperatureChart"},{"name":"StatusBanner"},{"name":"Dialog"},{"name":"Field"},{"name":"EmptyState"},{"name":"StatCard"},{"name":"Chip"}]} */
(function () {
  var React = window.React;
  var h = React.createElement;
  var useState = React.useState, useEffect = React.useEffect, useRef = React.useRef;

  /* ------------------------------------------------------------------ */
  /* Vocabulaire (annexe A) et utilitaires                              */
  /* ------------------------------------------------------------------ */
  var LEVELS = ['normal', 'information', 'surveillance', 'inspection', 'urgence'];
  var LEVEL_LABEL = { normal: 'Normal', information: 'Information', surveillance: 'Surveillance', inspection: 'Inspection', urgence: 'Urgence' };
  var LEVEL_REACTION = {
    normal: 'Aucune action',
    information: 'Aucune action ; événement enregistré',
    surveillance: "Suivre l'évolution",
    inspection: 'Contrôle sur place dans la journée',
    urgence: 'Intervention immédiate'
  };
  var STATE_LABEL = { ouverte: 'Ouverte', acquittee: 'Acquittée', assignee: 'Assignée', cloturee: 'Clôturée' };

  function cx() {
    var out = [];
    for (var i = 0; i < arguments.length; i++) if (arguments[i]) out.push(arguments[i]);
    return out.join(' ');
  }
  function fmt(v, digits) {
    if (v === null || v === undefined || isNaN(v)) return '–';
    return Number(v).toFixed(digits === undefined ? 1 : digits).replace('.', ',');
  }
  var uid = 0;
  function useUid(prefix) {
    var r = useRef(null);
    if (r.current === null) { uid += 1; r.current = (prefix || 'sasi') + '-' + uid; }
    return r.current;
  }

  /* Pictogrammes 24 x 24, tracé currentColor */
  var ICONS = {
    check: 'M5 12.5l4.5 4.5L19 7.5',
    x: 'M6 6l12 12M18 6L6 18',
    bell: 'M6 16v-5a6 6 0 0112 0v5l1.5 2h-15zM10 20.5h4',
    user: 'M12 12a4 4 0 100-8 4 4 0 000 8zM4.5 20a7.5 7.5 0 0115 0',
    cameraOff: 'M3 3l18 18M8 5h6.5a2 2 0 012 2v2.5l4-2.5v10.5M3 8v8.5a2 2 0 002 2h9.5',
    wifiOff: 'M3 3l18 18M5 12.5a10 10 0 015-2.6M8.5 16a5 5 0 017 0M19 12.5a10 10 0 00-6-2.8M12 19.5h.01',
    wrench: 'M14.5 6a4 4 0 005.2 5.2L11 20a2.1 2.1 0 01-3-3l8.7-8.7z',
    book: 'M4 5.5C6.5 4 9.5 4 12 5.5v14C9.5 18 6.5 18 4 19.5zM20 5.5C17.5 4 14.5 4 12 5.5v14c2.5-1.5 5.5-1.5 8 0z',
    flask: 'M9 3h6M10 3v6l-5 9a2 2 0 002 3h10a2 2 0 002-3l-5-9V3',
    search: 'M11 18a7 7 0 100-14 7 7 0 000 14zM20 20l-4-4',
    chevron: 'M6 9l6 6 6-6',
    trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13',
    clock: 'M12 21a9 9 0 100-18 9 9 0 000 18zM12 7v5l3 2',
    alert: 'M12 3l10 18H2zM12 10v5M12 18h.01',
    okCircle: 'M12 21a9 9 0 100-18 9 9 0 000 18zM8 12.5l3 3 5-6',
    arrowUp: 'M12 19V5M6 11l6-6 6 6',
    arrowDown: 'M12 5v14M6 13l6 6 6-6',
    minus: 'M6 12h12',
    calendar: 'M4 6.5a2 2 0 012-2h12a2 2 0 012 2V19a2 2 0 01-2 2H6a2 2 0 01-2-2zM4 10h16M8 3v3M16 3v3',
    download: 'M12 4v11M7 11l5 5 5-5M5 20h14',
    print: 'M7 8V4h10v4M7 17H5a1 1 0 01-1-1v-6a1 1 0 011-1h14a1 1 0 011 1v6a1 1 0 01-1 1h-2M7 14h10v6H7z',
    polygon: 'M4.5 9.5L12 4l7.5 5.5-3 9.5h-9zM4.5 9.5h.01M12 4h.01M19.5 9.5h.01M16.5 19h.01M7.5 19h.01',
    undo: 'M9 7L4 12l5 5M4 12h10a6 6 0 016 6',
    hand: 'M8 13V6.5a1.5 1.5 0 013 0V11M11 10.5V5a1.5 1.5 0 013 0v6M14 10.5V6.5a1.5 1.5 0 013 0V14a6 6 0 01-6 6h-.5A6 6 0 016.7 16.8L4 12.5l1.2-1A1.4 1.4 0 017.3 12L8 13',
    plus: 'M12 5v14M5 12h14',
    pencil: 'M4 20l1-4L16.5 4.5a2 2 0 013 3L8 19zM14 7l3 3',
    camera: 'M4 7.5h3l2-2.5h6l2 2.5h3V19H4zM12 16.5a3.5 3.5 0 100-7 3.5 3.5 0 000 7z'
  };
  function Icon(props) {
    var size = props.size || 20;
    return h('svg', { className: cx('sasi-icon', props.className), width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', strokeWidth: props.strokeWidth || 2, strokeLinecap: 'round', strokeLinejoin: 'round', 'aria-hidden': 'true', focusable: 'false' },
      h('path', { d: ICONS[props.name] }));
  }

  /* Silhouettes de niveau : cercle, carré arrondi, losange, triangle, octogone */
  var SHAPES = {
    normal: function () { return h('circle', { cx: 12, cy: 12, r: 9.5 }); },
    information: function () { return h('rect', { x: 3, y: 3, width: 18, height: 18, rx: 4 }); },
    surveillance: function () { return h('path', { d: 'M12 1.8L22.2 12 12 22.2 1.8 12z', strokeLinejoin: 'round' }); },
    inspection: function () { return h('path', { d: 'M12 2.4L22.4 20.6H1.6z', strokeLinejoin: 'round' }); },
    urgence: function () { return h('path', { d: 'M8.2 2h7.6L22 8.2v7.6L15.8 22H8.2L2 15.8V8.2z', strokeLinejoin: 'round' }); }
  };
  var GLYPHS = {
    normal: 'M7.8 12.4l2.9 2.9 5.6-6',
    information: 'M12 11v5.6M12 7.6h.01',
    surveillance: 'M12 8.8a3.2 3.2 0 100 6.4 3.2 3.2 0 000-6.4z',
    inspection: 'M12 9.4v4.8M12 17.4h.01',
    urgence: 'M12 7.2v6.2M12 16.6h.01'
  };
  function LevelIcon(props) {
    var lv = props.level;
    var y = lv === 'inspection' ? 1 : 0;
    return h('svg', { className: 'sasi-levelicon', width: props.size, height: props.size, viewBox: '0 0 24 24', 'aria-hidden': 'true', focusable: 'false' },
      h('g', { className: 'sasi-levelicon-shape', strokeWidth: 1.6 }, SHAPES[lv]()),
      h('path', { className: 'sasi-levelicon-glyph', d: GLYPHS[lv], fill: 'none', strokeWidth: lv === 'urgence' ? 2.8 : 2.4, strokeLinecap: 'round', strokeLinejoin: 'round', transform: y ? 'translate(0 1)' : undefined }));
  }

  /* ------------------------------------------------------------------ */
  /* Button                                                             */
  /* ------------------------------------------------------------------ */
  function Button(props) {
    var p = Object.assign({}, props);
    var variant = p.variant || 'secondary', size = p.size || 'md', icon = p.icon;
    delete p.variant; delete p.size; delete p.icon; delete p.className; delete p.children;
    if (!p.type) p.type = 'button';
    p.className = cx('sasi-btn', 'sasi-btn-' + variant, 'sasi-btn-' + size, props.className);
    return h('button', p, icon ? h(Icon, { name: icon, size: 18 }) : null, props.children);
  }

  /* ------------------------------------------------------------------ */
  /* LevelBadge : pastille de niveau                                    */
  /* ------------------------------------------------------------------ */
  function LevelBadge(props) {
    var lv = props.level || 'normal';
    var size = props.size || 'md';
    var tone = props.tone || 'soft';
    var px = { sm: 16, md: 20, lg: 32 }[size];
    var label = props.label || LEVEL_LABEL[lv];
    return h('span', { className: cx('sasi-badge', 'sasi-lv-' + lv, 'sasi-badge-' + size, 'sasi-badge-' + tone, props.className) },
      h(LevelIcon, { level: lv, size: px }),
      props.iconOnly ? h('span', { className: 'sasi-sr' }, label) : h('span', { className: 'sasi-badge-label' }, label));
  }

  /* ------------------------------------------------------------------ */
  /* StateChip (interne) : état d'une alerte                            */
  /* ------------------------------------------------------------------ */
  function StateChip(props) {
    var s = props.state;
    var text = STATE_LABEL[s] + (s === 'assignee' && props.assignee ? ' à ' + props.assignee : '');
    return h('span', { className: cx('sasi-state', 'sasi-state-' + s) },
      s === 'assignee' ? h(Icon, { name: 'user', size: 14 }) : null,
      s === 'cloturee' ? h(Icon, { name: 'check', size: 14 }) : null,
      text);
  }

  /* ------------------------------------------------------------------ */
  /* AlertCard                                                          */
  /* ------------------------------------------------------------------ */
  function AlertCard(props) {
    var kind = props.kind || 'incendie';
    var lv = props.level || 'inspection';
    var state = props.state || 'ouverte';
    var compact = props.density === 'compact';
    var technical = kind === 'technique';
    var canTake = state === 'ouverte' && !!props.onTakeOver;
    var cls = cx('sasi-alert', technical ? 'sasi-alert-technical' : 'sasi-lv-' + lv, technical ? '' : 'sasi-alert-' + lv,
      compact && 'sasi-alert-compact', state === 'cloturee' && 'sasi-alert-closed', props.className);
    var band = !technical && lv === 'urgence' && !compact && state !== 'cloturee';
    var lead = technical
      ? h('span', { className: 'sasi-tech-tag' }, h(Icon, { name: props.icon || 'cameraOff', size: 20 }), props.techLabel || 'Caméra muette')
      : (band ? null : h(LevelBadge, { level: lv, size: compact ? 'sm' : 'md', tone: (lv === 'urgence' && state !== 'cloturee') ? 'solid' : 'soft' }));
    return h('article', { className: cls, 'aria-label': (technical ? 'Problème technique' : LEVEL_LABEL[lv]) + ' : ' + props.equipment },
      band ? h('div', { className: 'sasi-alert-band' },
        h(LevelIcon, { level: 'urgence', size: 24 }),
        h('strong', null, 'Urgence'),
        h('span', null, ' — ' + LEVEL_REACTION.urgence)) : null,
      h('div', { className: 'sasi-alert-body' },
        lead ? h('div', { className: 'sasi-alert-lead' }, lead) : null,
        h('div', { className: 'sasi-alert-main' },
          h('div', { className: 'sasi-alert-head' },
            h('button', { type: 'button', className: 'sasi-alert-title', onClick: props.onOpen }, props.equipment),
            props.zone ? h('span', { className: 'sasi-alert-zone' }, props.zone) : null,
            (compact && props.overdue) ? h('span', { className: 'sasi-alert-overdue', title: 'Non acquittée depuis plus de 10 minutes' }, h(Icon, { name: 'bell', size: 16 }), 'Relance envoyée') : null,
            props.since ? h('span', { className: 'sasi-alert-since' }, h(Icon, { name: 'clock', size: 14 }), props.since) : null),
          props.reason ? h('p', { className: 'sasi-alert-reason' }, props.reason) : null,
          h('div', { className: 'sasi-alert-meta' },
            (props.measured !== undefined && !technical) ? h('span', { className: 'sasi-alert-temps', title: compact && props.expected !== undefined ? 'Mesurée ' + fmt(props.measured) + ' °C, attendue ' + fmt(props.expected) + ' °C' : undefined },
              h('span', null, compact ? null : 'Mesurée ', h('b', { className: 'sasi-fig' }, fmt(props.measured) + ' °C')),
              (props.expected !== undefined && !compact) ? h('span', null, 'Attendue ', h('b', { className: 'sasi-fig' }, fmt(props.expected) + ' °C')) : null,
              props.expected !== undefined ? h('span', { className: 'sasi-alert-delta' }, (props.measured - props.expected >= 0 ? '+' : '\u2212') + fmt(Math.abs(props.measured - props.expected)) + ' °C') : null) : null,
            h(StateChip, { state: state, assignee: props.assignee }),
            (!compact && props.overdue) ? h('span', { className: 'sasi-alert-overdue' }, h(Icon, { name: 'bell', size: 16 }), 'Non acquittée depuis plus de 10 min : relance envoyée') : null)),
        h('div', { className: 'sasi-alert-actions' },
          canTake ? h(Button, { variant: lv === 'urgence' && !technical ? 'primary' : 'secondary', size: compact ? 'sm' : 'md', onClick: props.onTakeOver }, 'Prendre en charge') : null,
          props.onOpen && !compact ? h(Button, { variant: 'quiet', onClick: props.onOpen }, 'Ouvrir la fiche') : null)));
  }

  /* ------------------------------------------------------------------ */
  /* DataTable                                                          */
  /* ------------------------------------------------------------------ */
  function DataTable(props) {
    var cols = props.columns || [], rows = props.rows || [];
    var sort = props.sort;
    var caption = props.caption;
    if (!rows.length && props.empty) return props.empty;
    return h('div', { className: cx('sasi-table-wrap', props.className) },
      h('table', { className: cx('sasi-table', props.dense && 'sasi-table-dense') },
        caption ? h('caption', { className: 'sasi-sr' }, caption) : null,
        h('thead', null, h('tr', null, cols.map(function (c) {
          var active = sort && sort.key === c.key;
          var ariaSort = active ? (sort.dir === 'asc' ? 'ascending' : 'descending') : (c.sortable ? 'none' : undefined);
          return h('th', { key: c.key, scope: 'col', 'aria-sort': ariaSort, className: cx(c.numeric && 'sasi-num', c.align === 'right' && 'sasi-num'), style: c.width ? { width: c.width } : undefined },
            c.sortable ? h('button', { type: 'button', className: cx('sasi-th-btn', active && 'is-active'), onClick: function () { props.onSort && props.onSort(c.key, active && sort.dir === 'asc' ? 'desc' : 'asc'); } },
              c.label,
              h('span', { className: cx('sasi-sort', active && sort.dir === 'asc' && 'is-asc'), 'aria-hidden': 'true' }, h(Icon, { name: 'chevron', size: 14 }))) : c.label);
        }))),
        h('tbody', null, rows.map(function (r, i) {
          var id = props.rowKey ? r[props.rowKey] : i;
          var open = props.onRowOpen;
          return h('tr', { key: id, className: cx(props.selectedKey === id && 'is-selected', open && 'is-clickable', props.rowClassName && props.rowClassName(r)), tabIndex: open ? 0 : undefined,
            onClick: open ? function () { open(r); } : undefined,
            onKeyDown: open ? function (e) { if (e.key === 'Enter') open(r); } : undefined },
            cols.map(function (c) {
              return h('td', { key: c.key, className: cx((c.numeric || c.align === 'right') && 'sasi-num') }, c.render ? c.render(r) : r[c.key]);
            }));
        }))));
  }

  /* ------------------------------------------------------------------ */
  /* TemperatureChart                                                   */
  /* ------------------------------------------------------------------ */
  var DASHES = ['', '10 5', '2 4', '10 4 2 4', '5 3'];
  function marker(kind, x, y, r, cls) {
    if (kind === 0) return h('circle', { cx: x, cy: y, r: r, className: cls });
    if (kind === 1) return h('rect', { x: x - r, y: y - r, width: 2 * r, height: 2 * r, className: cls });
    if (kind === 2) return h('path', { d: 'M' + x + ' ' + (y - r - 1) + 'L' + (x + r + 1) + ' ' + (y + r) + 'L' + (x - r - 1) + ' ' + (y + r) + 'z', className: cls });
    if (kind === 3) return h('path', { d: 'M' + x + ' ' + (y - r - 1) + 'L' + (x + r + 1) + ' ' + y + 'L' + x + ' ' + (y + r + 1) + 'L' + (x - r - 1) + ' ' + y + 'z', className: cls });
    return h('path', { d: 'M' + (x - r) + ' ' + (y - r) + 'L' + (x + r) + ' ' + (y + r) + 'M' + (x + r) + ' ' + (y - r) + 'L' + (x - r) + ' ' + (y + r), className: cls, fill: 'none' });
  }
  function niceStep(span, target) {
    var raw = span / target, mag = Math.pow(10, Math.floor(Math.log(raw) / Math.LN10)), n = raw / mag;
    return (n <= 1 ? 1 : n <= 2 ? 2 : n <= 5 ? 5 : 10) * mag;
  }
  function fmtTick(t, spanMs) {
    var d = new Date(t);
    var p = function (n) { return (n < 10 ? '0' : '') + n; };
    if (spanMs <= 3 * 86400000) return p(d.getHours()) + ':' + p(d.getMinutes());
    return p(d.getDate()) + '/' + p(d.getMonth() + 1);
  }
  function fmtStamp(t) {
    try { return new Date(t).toLocaleString('fr-FR', { weekday: 'long', hour: '2-digit', minute: '2-digit', day: 'numeric', month: 'short' }); } catch (e) { return String(t); }
  }
  function nearestIndex(pts, t) {
    var lo = 0, hi = pts.length - 1;
    while (hi - lo > 1) { var mid = (lo + hi) >> 1; if (pts[mid].t < t) lo = mid; else hi = mid; }
    return Math.abs(pts[lo].t - t) <= Math.abs(pts[hi].t - t) ? lo : hi;
  }

  function TemperatureChart(props) {
    var W = 960, H = props.height || 340;
    var m = { l: 56, r: 148, t: 20, b: 32 };
    var pw = W - m.l - m.r, ph = H - m.t - m.b;
    var series = props.series || [];
    var pid = useUid('sasi-chart');
    var st = useState(null), hoverT = st[0], setHoverT = st[1];
    var st2 = useState(series.length ? series[0].id : null), selfSel = st2[0], setSelfSel = st2[1];
    var selectedId = props.selectedId !== undefined ? props.selectedId : selfSel;
    var single = series.length === 1;
    var expected = props.expected || null;
    var svgRef = useRef(null);

    if (!series.length || !series[0].points || !series[0].points.length) {
      return h('div', { className: 'sasi-chart sasi-chart-empty' }, props.emptyMessage || 'Aucune mesure sur cette période. Choisissez une autre période.');
    }

    /* domaine temps */
    var t0 = Infinity, t1 = -Infinity, vmin = Infinity, vmax = -Infinity;
    function scan(pts) { pts.forEach(function (p) { if (p.t < t0) t0 = p.t; if (p.t > t1) t1 = p.t; if (p.v !== null && p.v !== undefined) { if (p.v < vmin) vmin = p.v; if (p.v > vmax) vmax = p.v; } }); }
    series.forEach(function (s) { scan(s.points); });
    if (expected) scan(expected.points);
    if (props.range) { t0 = props.range[0]; t1 = props.range[1]; }
    var nr = props.normalRange;
    if (nr) { vmin = Math.min(vmin, nr[0]); vmax = Math.max(vmax, nr[1]); }
    var span0 = Math.max(vmax - vmin, 4);
    var thresholds = (props.thresholds || []).slice();
    var offscreen = [];
    var inside = thresholds.filter(function (th) { var ok = th.value <= vmax + span0 * 0.6; if (!ok) offscreen.push(th); return ok; });
    inside.forEach(function (th) { vmax = Math.max(vmax, th.value); });
    var pad = (vmax - vmin) * 0.08;
    var y0 = Math.floor((vmin - pad) / 5) * 5, y1 = Math.ceil((vmax + pad) / 5) * 5;
    var X = function (t) { return m.l + (t - t0) / (t1 - t0 || 1) * pw; };
    var Y = function (v) { return m.t + (1 - (v - y0) / (y1 - y0 || 1)) * ph; };

    /* interruptions : nulls ou écart > 4 pas médians */
    var ref = series[0].points, dts = [];
    for (var i = 1; i < ref.length; i++) dts.push(ref[i].t - ref[i - 1].t);
    dts.sort(function (a, b) { return a - b; });
    var med = dts.length ? dts[dts.length >> 1] : 60000;
    var gapLimit = props.gapAfter || med * 4;
    var gaps = [];
    function segments(pts, collectGaps) {
      var segs = [], cur = [], prevValid = null, gapStart = null;
      pts.forEach(function (p) {
        if (p.v === null || p.v === undefined) {
          if (cur.length) { segs.push(cur); cur = []; }
          if (prevValid && gapStart === null) gapStart = prevValid.t;
          return;
        }
        if (gapStart !== null) { if (collectGaps) gaps.push([gapStart, p.t]); gapStart = null; }
        else if (prevValid && p.t - prevValid.t > gapLimit) {
          if (cur.length) { segs.push(cur); cur = []; }
          if (collectGaps) gaps.push([prevValid.t, p.t]);
        }
        cur.push(p); prevValid = p;
      });
      if (cur.length) segs.push(cur);
      return segs;
    }
    function pathOf(seg) { return seg.map(function (p, k) { return (k ? 'L' : 'M') + X(p.t).toFixed(1) + ' ' + Y(p.v).toFixed(1); }).join(''); }

    var segsBySeries = series.map(function (s, k) { return segments(s.points, k === 0); });

    /* graduations */
    var yStep = niceStep(y1 - y0, 5), yTicks = [];
    for (var yv = Math.ceil(y0 / yStep) * yStep; yv <= y1 + 1e-6; yv += yStep) yTicks.push(yv);
    var spanMs = t1 - t0, xTicks = [];
    var STEPS = [900000, 1800000, 3600000, 2 * 3600000, 3 * 3600000, 6 * 3600000, 12 * 3600000, 86400000, 2 * 86400000, 7 * 86400000];
    var unit = STEPS[STEPS.length - 1];
    for (var si = 0; si < STEPS.length; si++) if (spanMs / STEPS[si] <= 8) { unit = STEPS[si]; break; }
    var tzOff = -new Date(t0).getTimezoneOffset() * 60000;
    for (var xv = Math.ceil((t0 + tzOff) / unit) * unit - tzOff; xv <= t1; xv += unit) xTicks.push(xv);

    /* étiquettes directes, sans chevauchement */
    var labels = series.map(function (s, k) {
      var pts = s.points, last = null;
      for (var j = pts.length - 1; j >= 0; j--) if (pts[j].v !== null && pts[j].v !== undefined) { last = pts[j]; break; }
      return { k: k, y: last ? Y(last.v) : m.t, v: last ? last.v : null };
    }).sort(function (a, b) { return a.y - b.y; });
    for (var q = 1; q < labels.length; q++) if (labels[q].y - labels[q - 1].y < 18) labels[q].y = labels[q - 1].y + 18;

    /* survol */
    var hover = null;
    if (hoverT !== null) {
      var rows = series.map(function (s, k) {
        var idx = nearestIndex(s.points, hoverT), p = s.points[idx];
        var ok = p && p.v !== null && p.v !== undefined && Math.abs(p.t - hoverT) <= gapLimit;
        return { k: k, label: s.label, v: ok ? p.v : null, t: p.t };
      });
      var expV = null;
      if (expected) { var ie = nearestIndex(expected.points, hoverT), pe = expected.points[ie]; if (pe && pe.v !== null && Math.abs(pe.t - hoverT) <= gapLimit) expV = pe.v; }
      hover = { t: rows[0].t, rows: rows, exp: expV };
    }
    function onMove(e) {
      var box = svgRef.current.getBoundingClientRect();
      var x = (e.clientX - box.left) / box.width * W;
      if (x < m.l || x > W - m.r) { setHoverT(null); return; }
      setHoverT(t0 + (x - m.l) / pw * (t1 - t0));
    }
    function onKey(e) {
      if (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight') return;
      e.preventDefault();
      var cur = hoverT === null ? t1 : hoverT, stepT = med * (e.shiftKey ? 12 : 1);
      setHoverT(Math.min(t1, Math.max(t0, cur + (e.key === 'ArrowRight' ? stepT : -stepT))));
    }
    function select(id) { if (props.onSelect) props.onSelect(id); else setSelfSel(id); }

    var ttH = 26 + (hover ? (hover.rows.length + (hover.exp !== null ? 1 : 0)) * 20 : 0), ttW = 232;
    var hx = hover ? X(hover.t) : 0;
    var ttX = hover ? (hx > W / 2 ? hx - ttW - 12 : hx + 12) : 0;

    return h('figure', { className: cx('sasi-chart', props.className) },
      h('div', { className: 'sasi-legend', role: 'group', 'aria-label': 'Légende des courbes' },
        series.map(function (s, k) {
          var on = selectedId === s.id;
          return h('button', { key: s.id, type: 'button', className: cx('sasi-legend-item', on && 'is-selected'), 'aria-pressed': on, onClick: function () { select(s.id); }, style: { '--c': 'var(--serie-' + ((k % 5) + 1) + ')' } },
            h('svg', { width: 28, height: 14, viewBox: '0 0 28 14', 'aria-hidden': 'true' },
              h('line', { x1: 0, x2: 28, y1: 7, y2: 7, className: 'sasi-legend-line', strokeDasharray: DASHES[k % 5] }),
              marker(k % 5, 14, 7, 3.6, 'sasi-legend-mark')),
            h('span', null, s.label));
        }),
        expected ? h('span', { className: 'sasi-legend-item sasi-legend-static' }, h('svg', { width: 28, height: 14, viewBox: '0 0 28 14', 'aria-hidden': 'true' }, h('line', { x1: 0, x2: 28, y1: 7, y2: 7, className: 'sasi-expected', strokeDasharray: '2 3' })), h('span', null, 'Température attendue')) : null),
      h('svg', { ref: svgRef, className: 'sasi-chart-svg', viewBox: '0 0 ' + W + ' ' + H, role: 'group', tabIndex: 0, 'aria-label': props.summary || 'Courbe de température', onMouseMove: onMove, onMouseLeave: function () { setHoverT(null); }, onKeyDown: onKey, onBlur: function () { setHoverT(null); } },
        h('defs', null,
          h('pattern', { id: pid + '-stop', width: 8, height: 8, patternUnits: 'userSpaceOnUse', patternTransform: 'rotate(45)' }, h('rect', { width: 8, height: 8, className: 'sasi-stop-bg' }), h('line', { x1: 0, y1: 0, x2: 0, y2: 8, className: 'sasi-stop-line' })),
          h('pattern', { id: pid + '-gap', width: 6, height: 6, patternUnits: 'userSpaceOnUse' }, h('circle', { cx: 3, cy: 3, r: 1, className: 'sasi-gap-dot' })),
          h('clipPath', { id: pid + '-clip' }, h('rect', { x: m.l, y: m.t, width: pw, height: ph }))),
        /* fonds */
        nr ? h('g', null,
          h('rect', { x: m.l, y: Y(nr[1]), width: pw, height: Y(nr[0]) - Y(nr[1]), className: 'sasi-range' }),
          h('text', { x: m.l + 8, y: Y(nr[1]) + 16, className: 'sasi-note' }, 'Plage normale ' + fmt(nr[0], 0) + ' à ' + fmt(nr[1], 0) + ' °C')) : null,
        (props.stops || []).map(function (s, k) { return h('rect', { key: 'stop' + k, x: X(Math.max(s.from, t0)), y: m.t, width: Math.max(0, X(Math.min(s.to, t1)) - X(Math.max(s.from, t0))), height: ph, fill: 'url(#' + pid + '-stop)' }); }),
        gaps.map(function (g, k) { return h('g', { key: 'gap' + k }, h('rect', { x: X(g[0]), y: m.t, width: Math.max(2, X(g[1]) - X(g[0])), height: ph, fill: 'url(#' + pid + '-gap)' }), h('title', null, 'Aucune mesure reçue')); }),
        /* grille */
        yTicks.map(function (v) { return h('g', { key: 'y' + v }, h('line', { x1: m.l, x2: W - m.r, y1: Y(v), y2: Y(v), className: 'sasi-grid' }), h('text', { x: m.l - 10, y: Y(v) + 5, textAnchor: 'end', className: 'sasi-tick' }, fmt(v, 0))); }),
        h('text', { x: m.l - 10, y: 12, textAnchor: 'end', className: 'sasi-tick' }, '°C'),
        xTicks.map(function (v) { return h('g', { key: 'x' + v }, h('line', { x1: X(v), x2: X(v), y1: m.t, y2: m.t + ph, className: 'sasi-grid sasi-grid-v' }), h('text', { x: X(v), y: H - 8, textAnchor: 'middle', className: 'sasi-tick' }, fmtTick(v, spanMs))); }),
        /* seuils fixes */
        inside.map(function (th) { return h('g', { key: 'th' + th.level, className: 'sasi-lv-' + th.level }, h('line', { x1: m.l, x2: W - m.r, y1: Y(th.value), y2: Y(th.value), className: 'sasi-threshold' }), h('text', { x: W - m.r + 8, y: Y(th.value) + 5, className: 'sasi-threshold-label' }, (th.label || LEVEL_LABEL[th.level]) + ' ' + fmt(th.value, 0) + ' °C')); }),
        offscreen.map(function (th, k) { var topEnd = m.t + 16 + offscreen.length * 16, clash = inside.some(function (t2) { var yy = Y(t2.value); return yy > m.t - 8 && yy < topEnd; }); return h('text', { key: 'off' + k, x: W - m.r + 8, y: clash ? m.t + ph - 6 - (offscreen.length - 1 - k) * 16 : m.t + 12 + k * 16, className: 'sasi-note' }, '▲ ' + (th.label || LEVEL_LABEL[th.level]) + ' ' + fmt(th.value, 0) + ' °C'); }),
        /* périodes d'alerte */
        (props.periods || []).map(function (p, k) {
          var xa = X(Math.max(p.from, t0)), xb = X(Math.min(p.to, t1));
          return h('g', { key: 'per' + k, className: cx('sasi-period', 'sasi-lv-' + p.level, props.onPeriodClick && 'is-clickable'), tabIndex: props.onPeriodClick ? 0 : undefined, role: props.onPeriodClick ? 'button' : undefined, 'aria-label': 'Alerte ' + LEVEL_LABEL[p.level] + ' : ouvrir', onClick: function () { props.onPeriodClick && props.onPeriodClick(p); }, onKeyDown: function (e) { if (e.key === 'Enter' && props.onPeriodClick) props.onPeriodClick(p); } },
            h('rect', { x: xa, y: m.t, width: Math.max(3, xb - xa), height: ph, className: 'sasi-period-fill' }),
            h('rect', { x: xa, y: m.t, width: Math.max(3, xb - xa), height: 7, className: 'sasi-period-bar' }));
        }),
        /* écart entre mesure et attendu (équipement seul) */
        (single && expected) ? (function () {
          var a = series[0].points.filter(function (p) { return p.v !== null && p.v !== undefined; }), out = [], bwd = [];
          a.forEach(function (p, k) { var ep = expected.points[nearestIndex(expected.points, p.t)]; if (ep && ep.v != null) { out.push(X(p.t).toFixed(1) + ' ' + Y(p.v).toFixed(1)); bwd.push(X(p.t).toFixed(1) + ' ' + Y(ep.v).toFixed(1)); } });
          return h('path', { d: 'M' + out.join('L') + 'L' + bwd.reverse().join('L') + 'z', className: 'sasi-deviation', clipPath: 'url(#' + pid + '-clip)' });
        })() : null,
        expected ? segments(expected.points, false).map(function (sg, k) { return h('path', { key: 'e' + k, d: pathOf(sg), className: 'sasi-expected', strokeDasharray: '2 3', clipPath: 'url(#' + pid + '-clip)' }); }) : null,
        /* courbes */
        series.map(function (s, k) {
          var sel = single || selectedId === s.id, dim = !single && selectedId && !sel;
          return h('g', { key: s.id, className: cx('sasi-series', sel && 'is-selected', dim && 'is-dim'), style: { '--c': single ? 'var(--courbe-mesuree)' : 'var(--serie-' + ((k % 5) + 1) + ')' }, clipPath: 'url(#' + pid + '-clip)' },
            segsBySeries[k].map(function (sg, j) { return h('path', { key: j, d: pathOf(sg), className: 'sasi-line', strokeDasharray: single ? '' : DASHES[k % 5], strokeWidth: sel ? 3.2 : 2 }); }));
        }),
        /* étiquettes directes */
        !single ? labels.map(function (lb) {
          var s = series[lb.k], sel = selectedId === s.id, kk = lb.k % 5;
          return h('g', { key: 'lb' + lb.k, className: cx('sasi-endlabel', sel && 'is-selected'), style: { '--c': 'var(--serie-' + (kk + 1) + ')' }, onClick: function () { select(s.id); } },
            marker(kk, W - m.r + 12, lb.y, 4, 'sasi-endmark'),
            h('text', { x: W - m.r + 24, y: lb.y + 5, className: 'sasi-endtext' }, s.label));
        }) : null,
        /* survol */
        hover ? h('g', { className: 'sasi-hover', pointerEvents: 'none' },
          h('line', { x1: hx, x2: hx, y1: m.t, y2: m.t + ph, className: 'sasi-cursor' }),
          hover.rows.map(function (r) { return r.v !== null ? h('g', { key: 'hm' + r.k, style: { '--c': single ? 'var(--courbe-mesuree)' : 'var(--serie-' + ((r.k % 5) + 1) + ')' } }, marker(r.k % 5, hx, Y(r.v), 4.5, 'sasi-hovermark')) : null; }),
          h('g', { transform: 'translate(' + ttX + ' ' + Math.max(m.t, 24) + ')' },
            h('rect', { width: ttW, height: ttH, rx: 8, className: 'sasi-tt' }),
            h('text', { x: 12, y: 19, className: 'sasi-tt-time' }, fmtStamp(hover.t)),
            hover.rows.map(function (r, k) { return h('g', { key: 'tt' + k, style: { '--c': single ? 'var(--courbe-mesuree)' : 'var(--serie-' + ((r.k % 5) + 1) + ')' } },
              marker(r.k % 5, 20, 38 + k * 20, 4, 'sasi-ttmark'),
              h('text', { x: 32, y: 43 + k * 20, className: 'sasi-tt-label' }, r.label),
              h('text', { x: ttW - 12, y: 43 + k * 20, textAnchor: 'end', className: 'sasi-tt-val' }, r.v !== null ? fmt(r.v) + ' °C' : 'pas de mesure')); }),
            hover.exp !== null ? h('g', null, h('text', { x: 32, y: 43 + hover.rows.length * 20, className: 'sasi-tt-label' }, 'Attendue'), h('text', { x: ttW - 12, y: 43 + hover.rows.length * 20, textAnchor: 'end', className: 'sasi-tt-val' }, fmt(hover.exp) + ' °C')) : null)) : null,
        h('rect', { x: m.l, y: m.t, width: pw, height: ph, fill: 'transparent', className: 'sasi-hit' })),
      props.caption ? h('figcaption', { className: 'sasi-chart-cap' }, props.caption) : null);
  }

  /* ------------------------------------------------------------------ */
  /* StatusBanner : bandeau d'état                                      */
  /* ------------------------------------------------------------------ */
  var BANNER = {
    liaison: { icon: 'wifiOff', tone: 'technical', title: 'Liaison interrompue', role: 'alert' },
    technique: { icon: 'cameraOff', tone: 'technical', title: 'Caméra muette', role: 'alert' },
    apprentissage: { icon: 'book', tone: 'info', title: "Période d'apprentissage", role: 'status' },
    maintenance: { icon: 'wrench', tone: 'info', title: 'Équipement en maintenance', role: 'status' },
    demonstration: { icon: 'flask', tone: 'info', title: 'Mode démonstration', role: 'status' }
  };
  function StatusBanner(props) {
    var k = BANNER[props.kind || 'liaison'];
    return h('div', { className: cx('sasi-banner', 'sasi-banner-' + k.tone, props.className), role: k.role },
      h(Icon, { name: k.icon, size: 22 }),
      h('div', { className: 'sasi-banner-text' },
        h('strong', null, props.title || k.title),
        props.children ? h('span', null, ' ', props.children) : null,
        props.lastContact ? h('span', { className: 'sasi-banner-time' }, ' Dernier contact : ', h('b', { className: 'sasi-fig' }, props.lastContact), '.') : null),
      props.onAction ? h(Button, { variant: 'secondary', size: 'sm', onClick: props.onAction }, props.actionLabel || 'Réessayer') : null);
  }

  /* ------------------------------------------------------------------ */
  /* Dialog : boîte de dialogue de confirmation                         */
  /* ------------------------------------------------------------------ */
  function Dialog(props) {
    var id = useUid('sasi-dlg');
    var ref = useRef(null);
    var inline = props.presentation === 'inline';
    useEffect(function () {
      if (!props.open || inline) return;
      var prev = document.activeElement;
      var first = ref.current && ref.current.querySelector('[data-autofocus], input, textarea, select, button');
      if (first) first.focus();
      function key(e) {
        if (e.key === 'Escape') { props.onCancel && props.onCancel(); }
        if (e.key === 'Tab' && ref.current) {
          var f = ref.current.querySelectorAll('button, input, select, textarea, [tabindex]:not([tabindex="-1"])');
          if (!f.length) return;
          var a = f[0], z = f[f.length - 1];
          if (e.shiftKey && document.activeElement === a) { e.preventDefault(); z.focus(); }
          else if (!e.shiftKey && document.activeElement === z) { e.preventDefault(); a.focus(); }
        }
      }
      document.addEventListener('keydown', key);
      return function () { document.removeEventListener('keydown', key); if (prev && prev.focus) prev.focus(); };
    }, [props.open]);
    if (!props.open) return null;
    var destructive = !!props.destructive;
    var box = h('div', { ref: ref, className: cx('sasi-dialog', destructive && 'is-destructive'), role: 'dialog', 'aria-modal': inline ? undefined : 'true', 'aria-labelledby': id + '-t', 'aria-describedby': props.irreversible ? id + '-w' : undefined },
      h('h2', { id: id + '-t', className: 'sasi-dialog-title' }, props.title),
      props.irreversible ? h('p', { id: id + '-w', className: 'sasi-dialog-warn' }, h(Icon, { name: 'alert', size: 18 }), typeof props.irreversible === 'string' ? props.irreversible : 'Cette action est irréversible.') : null,
      h('div', { className: 'sasi-dialog-body' }, props.children),
      h('div', { className: 'sasi-dialog-actions' },
        h(Button, { variant: 'quiet', onClick: props.onCancel }, props.cancelLabel || 'Annuler'),
        h(Button, { variant: destructive ? 'destructive' : 'primary', icon: destructive ? 'trash' : undefined, onClick: props.onConfirm, disabled: props.confirmDisabled }, props.confirmLabel || 'Confirmer')));
    if (inline) return h('div', { className: 'sasi-dialog-inline' }, box);
    return h('div', { className: 'sasi-scrim', onMouseDown: function (e) { if (e.target === e.currentTarget && props.onCancel) props.onCancel(); } }, box);
  }

  /* ------------------------------------------------------------------ */
  /* Champs de formulaire                                               */
  /* ------------------------------------------------------------------ */
  function Field(props) {
    var id = useUid('sasi-f');
    var child = props.children;
    var described = [props.hint ? id + '-h' : null, props.error ? id + '-e' : null].filter(Boolean).join(' ') || undefined;
    var control = React.isValidElement(child) ? React.cloneElement(child, { id: id, 'aria-invalid': props.error ? 'true' : undefined, 'aria-describedby': described, required: props.required || child.props.required }) : child;
    return h('div', { className: cx('sasi-field', props.error && 'has-error', props.className) },
      h('label', { htmlFor: id, className: 'sasi-field-label' }, props.label, props.required ? h('span', { className: 'sasi-req' }, ' (obligatoire)') : null),
      props.hint ? h('p', { id: id + '-h', className: 'sasi-field-hint' }, props.hint) : null,
      control,
      props.error ? h('p', { id: id + '-e', className: 'sasi-field-error', role: 'alert' }, h(Icon, { name: 'alert', size: 16 }), props.error) : null);
  }
  function TextInput(props) { return h('input', Object.assign({ type: 'text' }, props, { className: cx('sasi-input', props.className) })); }
  function Textarea(props) { return h('textarea', Object.assign({ rows: 4 }, props, { className: cx('sasi-input sasi-textarea', props.className) })); }
  function Select(props) {
    var p = Object.assign({}, props); delete p.children; p.className = cx('sasi-input sasi-select', props.className);
    return h('span', { className: 'sasi-select-wrap' }, h('select', p, props.children), h(Icon, { name: 'chevron', size: 18, className: 'sasi-select-caret' }));
  }
  function Checkbox(props) {
    var p = Object.assign({}, props); delete p.label; delete p.className; p.type = 'checkbox';
    return h('label', { className: cx('sasi-check', props.className) }, h('input', p), h('span', { className: 'sasi-check-box', 'aria-hidden': 'true' }, h(Icon, { name: 'check', size: 14, strokeWidth: 3 })), h('span', null, props.label));
  }

  /* ------------------------------------------------------------------ */
  /* EmptyState : message d'écran vide                                  */
  /* ------------------------------------------------------------------ */
  function EmptyState(props) {
    return h('div', { className: cx('sasi-empty', props.className) },
      h('span', { className: cx('sasi-empty-icon', 'is-' + (props.tone || 'ok')) }, h(Icon, { name: props.icon || 'okCircle', size: 32 })),
      h('h3', { className: 'sasi-empty-title' }, props.title),
      props.children ? h('p', { className: 'sasi-empty-text' }, props.children) : null,
      props.action ? h('div', { className: 'sasi-empty-action' }, props.action) : null);
  }

  /* ------------------------------------------------------------------ */
  /* Chip : filtre en pastille (bascule)                                */
  /* ------------------------------------------------------------------ */
  function Chip(props) {
    var p = Object.assign({}, props);
    var selected = !!p.selected, icon = p.icon, label = p.label;
    delete p.selected; delete p.icon; delete p.label; delete p.className; delete p.children;
    p.type = 'button';
    p['aria-pressed'] = selected;
    p.className = cx('sasi-chip', selected && 'is-selected', props.className);
    return h('button', p, icon ? h(Icon, { name: icon, size: 16 }) : null, label !== undefined ? label : props.children);
  }

  /* ------------------------------------------------------------------ */
  /* StatCard : chiffre clé avec variation                              */
  /* ------------------------------------------------------------------ */
  var DELTA_ICON = { up: 'arrowUp', down: 'arrowDown', flat: 'minus' };
  var DELTA_WORD = { up: 'en hausse', down: 'en baisse', flat: 'stable' };
  function StatCard(props) {
    var lv = props.level;
    var size = props.size || 'lg';
    var d = props.delta;
    return h('div', { className: cx('sasi-stat', 'sasi-stat-' + size, lv && 'sasi-lv-' + lv, lv && !props.plain && 'is-level', lv && !props.plain && 'sasi-stat-' + lv, props.className) },
      h('div', { className: 'sasi-stat-head' },
        lv && !props.label ? h(LevelBadge, { level: lv, size: 'sm' }) : h('span', { className: 'sasi-stat-label' }, props.label),
        d ? h('span', { className: 'sasi-stat-delta' },
          h(Icon, { name: DELTA_ICON[d.direction || 'flat'], size: 14, strokeWidth: 2.4 }),
          h('span', { className: 'sasi-sr' }, DELTA_WORD[d.direction || 'flat'] + ' : '),
          d.text) : null),
      h('div', { className: 'sasi-stat-value' },
        h('span', { className: cx('sasi-stat-fig', size === 'xl' ? 'figure-xl' : size === 'md' ? 'figure-md' : 'figure-lg') }, props.value),
        props.unit ? h('span', { className: 'sasi-stat-unit' }, props.unit) : null),
      lv && props.label ? h('div', { className: 'sasi-stat-foot' }, h(LevelBadge, { level: lv, size: 'sm' })) : null,
      props.caption ? h('p', { className: 'sasi-stat-caption' }, props.caption) : null);
  }

  var api = { Button: Button, LevelBadge: LevelBadge, AlertCard: AlertCard, DataTable: DataTable, TemperatureChart: TemperatureChart, StatusBanner: StatusBanner, Dialog: Dialog, Field: Field, TextInput: TextInput, Textarea: Textarea, Select: Select, Checkbox: Checkbox, EmptyState: EmptyState, StatCard: StatCard, Chip: Chip, LEVELS: LEVELS, LEVEL_LABEL: LEVEL_LABEL, LEVEL_REACTION: LEVEL_REACTION, STATE_LABEL: STATE_LABEL, formatTemperature: fmt };
  window.SASI = window.SASI || {};
  Object.assign(window.SASI, api);
})();
