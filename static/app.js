/* Galleriradar Oslo – henter fra /api og tegner listen. */
(() => {
  const innhold = document.getElementById('innhold');
  const faner = document.getElementById('faner');
  const sokFelt = document.getElementById('sok');
  const galleriFelt = document.getElementById('galleri');
  const oppdaterKnapp = document.getElementById('oppdater');
  const varslingBoks = document.getElementById('varsling');
  const nyttTall = document.getElementById('nytt-tall');
  const bunntekst = document.getElementById('bunntekst');

  let visning = 'aktuelt';
  let tidsavbrudd = null;

  // Hver telefon husker selv når den sist så listen – da blir «NY» riktig for begge.
  const sistSett = () => localStorage.getItem('sistSett') || '';
  // Serveren lagrer lokal tid uten tidssone – klokka her må se lik ut for at
  // strengsammenlikningen mot forste_gang skal bli riktig.
  const naaLokal = () => {
    const d = new Date();
    const to = (n) => String(n).padStart(2, '0');
    return `${d.getFullYear()}-${to(d.getMonth() + 1)}-${to(d.getDate())}T` +
           `${to(d.getHours())}:${to(d.getMinutes())}:${to(d.getSeconds())}`;
  };
  const settSistSett = () => localStorage.setItem('sistSett', naaLokal());

  const tekst = (s) => (s == null ? '' : String(s));
  const trygg = (s) => tekst(s).replace(/[&<>"']/g, (c) =>
    ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));

  function erNy(u) {
    const sist = sistSett();
    return sist ? u.forste_gang > sist : false;
  }

  function dagerTekst(u) {
    if (u.dager_igjen === null || u.dager_igjen === undefined) return '';
    if (u.dager_igjen === 0) return 'Siste dag';
    if (u.dager_igjen === 1) return 'Siste dag i morgen';
    if (u.dager_igjen <= 7) return `${u.dager_igjen} dager igjen`;
    return '';
  }

  function kort(u) {
    const ny = erNy(u);
    const haster = dagerTekst(u);
    const bilde = u.bilde
      ? `<span class="kort__bilde"><img src="/bilde?u=${encodeURIComponent(u.bilde)}" alt=""
             loading="lazy" onerror="this.closest('.kort__bilde').remove()"></span>`
      : '';
    return `
      <article class="kort">
        <a href="${trygg(u.url)}" target="_blank" rel="noopener">${bilde}</a>
        <button class="stjerne" aria-pressed="${u.merket ? 'true' : 'false'}"
                data-nokkel="${trygg(u.nokkel)}" title="Vil se">${u.merket ? '★' : '☆'}</button>
        <div class="kort__tekst">
          <p class="kort__sted">
            <span>${trygg(u.galleri)}</span>
            ${ny ? '<span class="merkelapp">Ny</span>' : ''}
            ${u.type && u.type !== 'utstilling' ? `<span class="merkelapp merkelapp--rolig">${trygg(u.type)}</span>` : ''}
          </p>
          <h2 class="kort__tittel"><a href="${trygg(u.url)}" target="_blank" rel="noopener">${trygg(u.tittel)}</a></h2>
          ${u.kunstnere ? `<p class="kort__kunstnere">${trygg(u.kunstnere)}</p>` : ''}
          <p class="kort__dato">${trygg(u.periode)}
            ${haster ? `<span class="kort__slutt"> · ${haster}</span>` : ''}</p>
        </div>
      </article>`;
  }

  async function tegn() {
    const p = new URLSearchParams({ visning, sok: sokFelt.value.trim(), galleri: galleriFelt.value });
    const svar = await fetch(`/api/utstillinger?${p}`).then((r) => r.json());

    for (const el of document.querySelectorAll('[data-tall]')) {
      el.textContent = svar.tall[el.dataset.tall] ?? '';
    }
    bunntekst.textContent =
      `${svar.tall.totalt} utstillinger fra ${svar.tall.gallerier} visningssteder`;

    const nye = svar.utstillinger.filter(erNy);
    nyttTall.textContent = visning === 'nytt' ? (nye.length || '') : (nyttTall.textContent || '');

    // «Nytt» viser bare det som har dukket opp siden denne telefonen var innom sist.
    const liste = visning === 'nytt' ? nye : svar.utstillinger;

    if (!liste.length) {
      innhold.innerHTML = visning === 'nytt'
        ? '<p class="tomt">Ingenting nytt siden sist. Vi sier fra når noe dukker opp.</p>'
        : '<p class="tomt">Ingenting her akkurat nå.</p>';
      return;
    }
    const banner = (visning === 'nytt')
      ? `<div class="beskjed"><span>${nye.length} ${nye.length === 1 ? 'ny utstilling' : 'nye utstillinger'} siden sist</span>
           <button class="knapp" id="markerLest">Merk som sett</button></div>` : '';
    innhold.innerHTML = banner + `<div class="rutenett">${liste.map(kort).join('')}</div>`;

    const lest = document.getElementById('markerLest');
    if (lest) lest.onclick = () => { settSistSett(); tegn(); tellNye(); };
  }

  async function tellNye() {
    const p = new URLSearchParams({ visning: 'nytt', grense: 400 });
    const svar = await fetch(`/api/utstillinger?${p}`).then((r) => r.json());
    const antall = svar.utstillinger.filter(erNy).length;
    nyttTall.textContent = antall || '';
  }

  async function status() {
    const s = await fetch('/api/status').then((r) => r.json());
    varslingBoks.checked = !!s.varsling;
    oppdaterKnapp.classList.toggle('gaar', !!s.kjorer);
    return s;
  }

  // ── hendelser ──
  faner.addEventListener('click', (e) => {
    const knapp = e.target.closest('.fane');
    if (!knapp) return;
    for (const f of faner.children) f.classList.toggle('fane--valgt', f === knapp);
    visning = knapp.dataset.visning;
    tegn();
  });

  innhold.addEventListener('click', async (e) => {
    const stjerne = e.target.closest('.stjerne');
    if (!stjerne) return;
    const pa = stjerne.getAttribute('aria-pressed') !== 'true';
    stjerne.setAttribute('aria-pressed', String(pa));
    stjerne.textContent = pa ? '★' : '☆';
    await fetch('/api/merk', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ nokkel: stjerne.dataset.nokkel, pa }),
    });
    if (visning === 'merket') tegn();
  });

  const vent = (fn, ms) => (...a) => { clearTimeout(tidsavbrudd); tidsavbrudd = setTimeout(() => fn(...a), ms); };
  sokFelt.addEventListener('input', vent(tegn, 250));
  galleriFelt.addEventListener('change', tegn);

  oppdaterKnapp.addEventListener('click', async () => {
    oppdaterKnapp.classList.add('gaar');
    try {
      await fetch('/api/oppdater', { method: 'POST' });
    } finally {
      oppdaterKnapp.classList.remove('gaar');
      tegn();
      tellNye();
    }
  });

  varslingBoks.addEventListener('change', () => {
    fetch('/api/varsling', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ pa: varslingBoks.checked }),
    });
  });

  // Første besøk: alt er «sett», ellers ville hele basen lyst opp som nytt.
  if (!sistSett()) settSistSett();

  tegn();
  tellNye();
  status();
  setInterval(() => { status(); tellNye(); }, 60000);
  document.addEventListener('visibilitychange', () => { if (!document.hidden) tegn(); });

  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
})();
