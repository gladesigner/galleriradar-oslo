/* Galleriradar Oslo – hele listen ligger i data.json, resten skjer i telefonen. */
(() => {
  const innhold = document.getElementById('innhold');
  const faner = document.getElementById('faner');
  const sokFelt = document.getElementById('sok');
  const galleriFelt = document.getElementById('galleri');
  const oppdaterKnapp = document.getElementById('oppdater');
  const nyttTall = document.getElementById('nytt-tall');
  const bunntekst = document.getElementById('bunntekst');

  let data = { utstillinger: [], kilder: [], bygget: '', i_dag: '' };
  let visning = 'aktuelt';
  let tidsavbrudd = null;

  // «Nytt» er en fast luke: i dag og seks dager bakover. Da betyr fanen det
  // samme uansett hvilken telefon den åpnes på.
  const NYTT_VINDU = 6;
  const nyttGrense = () => {
    const d = new Date();
    d.setDate(d.getDate() - NYTT_VINDU);
    const to = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${to(d.getMonth() + 1)}-${to(d.getDate())}`;
  };

  const merker = () => { try { return JSON.parse(localStorage.getItem('merket') || '[]'); } catch { return []; } };
  const erMerket = (n) => merker().includes(n);
  const veksleMerke = (n) => {
    const m = merker();
    const i = m.indexOf(n);
    if (i >= 0) m.splice(i, 1); else m.push(n);
    localStorage.setItem('merket', JSON.stringify(m));
    return i < 0;
  };

  const trygg = (s) => (s == null ? '' : String(s)).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  const erNy = (u) => (u.forste_gang || '').slice(0, 10) >= nyttGrense();

  function dagerIgjen(u) {
    if (!u.slutt_dato || u.slutt_dato < data.i_dag) return null;
    const ms = new Date(u.slutt_dato) - new Date(data.i_dag);
    return Math.round(ms / 86400000);
  }

  function dagerTekst(u) {
    const d = dagerIgjen(u);
    if (d === null) return '';
    if (d === 0) return 'Siste dag';
    if (d === 1) return 'Siste dag i morgen';
    if (d <= 7) return `${d} dager igjen`;
    return '';
  }

  // ── utvalg ──
  function utvalg() {
    const i_dag = data.i_dag;
    let liste = data.utstillinger;

    if (visning === 'aktuelt') {
      liste = liste.filter((u) => !u.borte
        && (!u.slutt_dato || u.slutt_dato >= i_dag)
        && (!u.start_dato || u.start_dato <= i_dag));
      liste.sort((a, b) => (a.slutt_dato || '9999').localeCompare(b.slutt_dato || '9999'));
    } else if (visning === 'kommer') {
      liste = liste.filter((u) => u.start_dato && u.start_dato > i_dag);
      liste.sort((a, b) => a.start_dato.localeCompare(b.start_dato));
    } else if (visning === 'nytt') {
      // nyoppdagede som fortsatt henger
      liste = liste.filter((u) => erNy(u) && (!u.slutt_dato || u.slutt_dato >= i_dag));
      liste.sort((a, b) => b.forste_gang.localeCompare(a.forste_gang));
    } else if (visning === 'merket') {
      const m = merker();
      liste = liste.filter((u) => m.includes(u.nokkel));
      liste.sort((a, b) => (a.slutt_dato || '9999').localeCompare(b.slutt_dato || '9999'));
    } else if (visning === 'tidligere') {
      liste = liste.filter((u) => u.slutt_dato && u.slutt_dato < i_dag);
      liste.sort((a, b) => b.slutt_dato.localeCompare(a.slutt_dato));
    }

    const sted = galleriFelt.value;
    if (sted) liste = liste.filter((u) => u.kilde_id === sted);

    const q = sokFelt.value.trim().toLowerCase();
    if (q) {
      liste = liste.filter((u) => `${u.tittel} ${u.kunstnere} ${u.galleri} ${u.sammendrag}`
        .toLowerCase().includes(q));
    }
    return liste;
  }

  function tell(navn) {
    const i_dag = data.i_dag;
    if (navn === 'aktuelt') {
      return data.utstillinger.filter((u) => !u.borte
        && (!u.slutt_dato || u.slutt_dato >= i_dag)
        && (!u.start_dato || u.start_dato <= i_dag)).length;
    }
    if (navn === 'kommer') return data.utstillinger.filter((u) => u.start_dato > i_dag).length;
    if (navn === 'merket') return merker().length;
    return 0;
  }

  // ── tegning ──
  function kort(u) {
    const merket = erMerket(u.nokkel);
    const haster = dagerTekst(u);
    const bilde = u.bilde
      ? `<span class="kort__bilde"><img src="${trygg(u.bilde)}" alt="" loading="lazy"
             onerror="this.closest('.kort__bilde').remove()"></span>` : '';
    return `
      <article class="kort">
        <a href="${trygg(u.url)}" target="_blank" rel="noopener">${bilde}</a>
        <button class="stjerne" aria-pressed="${merket}" data-nokkel="${trygg(u.nokkel)}"
                title="Vil se">${merket ? '★' : '☆'}</button>
        <div class="kort__tekst">
          <p class="kort__sted">
            <span>${trygg(u.galleri)}</span>
            ${erNy(u) ? '<span class="merkelapp">Ny</span>' : ''}
            ${u.type && u.type !== 'utstilling' ? `<span class="merkelapp merkelapp--rolig">${trygg(u.type)}</span>` : ''}
          </p>
          <h2 class="kort__tittel"><a href="${trygg(u.url)}" target="_blank" rel="noopener">${trygg(u.tittel)}</a></h2>
          ${u.kunstnere ? `<p class="kort__kunstnere">${trygg(u.kunstnere)}</p>` : ''}
          <p class="kort__dato">${trygg(u.periode)}${haster ? `<span class="kort__slutt"> · ${haster}</span>` : ''}</p>
        </div>
      </article>`;
  }

  function tegn() {
    for (const el of document.querySelectorAll('[data-tall]')) {
      el.textContent = tell(el.dataset.tall) || '';
    }
    const nyeNaa = data.utstillinger.filter((u) => erNy(u) && (!u.slutt_dato || u.slutt_dato >= data.i_dag));
    nyttTall.textContent = nyeNaa.length || '';

    const liste = utvalg();
    if (!liste.length) {
      innhold.innerHTML = visning === 'nytt'
        ? '<p class="tomt">Ingenting nytt de siste sju dagene.</p>'
        : '<p class="tomt">Ingenting her akkurat nå.</p>';
      return;
    }
    const banner = visning === 'nytt'
      ? `<div class="beskjed"><span>${liste.length} ${liste.length === 1 ? 'ny utstilling' : 'nye utstillinger'}
           dukket opp de siste sju dagene</span></div>` : '';
    innhold.innerHTML = banner + `<div class="rutenett">${liste.map(kort).join('')}</div>`;
  }

  function fyllGallerier() {
    const navn = new Map();
    for (const u of data.utstillinger) navn.set(u.kilde_id, u.galleri);
    const valgt = galleriFelt.value;
    galleriFelt.innerHTML = '<option value="">Alle steder</option>' +
      [...navn.entries()].sort((a, b) => a[1].localeCompare(b[1], 'nb'))
        .map(([id, n]) => `<option value="${trygg(id)}">${trygg(n)}</option>`).join('');
    galleriFelt.value = valgt;
  }

  async function last() {
    oppdaterKnapp.classList.add('gaar');
    try {
      data = await fetch(`data.json?t=${Date.now()}`).then((r) => r.json());
      fyllGallerier();
      const hentet = (data.bygget || '').replace('T', ' kl. ').slice(0, 16);
      bunntekst.textContent =
        `${data.antall} utstillinger fra ${data.kilder.length} steder · hentet ${hentet}`;
      tegn();
    } catch {
      innhold.innerHTML = '<p class="tomt">Fikk ikke tak i listen. Prøv igjen når du har nett.</p>';
    } finally {
      oppdaterKnapp.classList.remove('gaar');
    }
  }

  // ── hendelser ──
  faner.addEventListener('click', (e) => {
    const knapp = e.target.closest('.fane');
    if (!knapp) return;
    for (const f of faner.children) f.classList.toggle('fane--valgt', f === knapp);
    visning = knapp.dataset.visning;
    tegn();
  });

  innhold.addEventListener('click', (e) => {
    const stjerne = e.target.closest('.stjerne');
    if (!stjerne) return;
    const pa = veksleMerke(stjerne.dataset.nokkel);
    stjerne.setAttribute('aria-pressed', String(pa));
    stjerne.textContent = pa ? '★' : '☆';
    for (const el of document.querySelectorAll('[data-tall="merket"]')) el.textContent = tell('merket') || '';
    if (visning === 'merket') tegn();
  });

  const vent = (fn, ms) => (...a) => { clearTimeout(tidsavbrudd); tidsavbrudd = setTimeout(() => fn(...a), ms); };
  sokFelt.addEventListener('input', vent(tegn, 200));
  galleriFelt.addEventListener('change', tegn);
  oppdaterKnapp.addEventListener('click', last);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) last(); });

  last();
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
})();
