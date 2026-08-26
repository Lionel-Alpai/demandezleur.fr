/* accueil.js — bandeau Assemblée (thèmes) ; la démo live arrive à l'incrément 2. */
(function () {
  'use strict';
  var bandeau = document.getElementById('bandeau-assemblee'); if (!bandeau) return;
  var zone = document.getElementById('assemblee-themes'), maj = document.getElementById('assemblee-maj');
  fetch(DL.api('/parlement/sujets?n=5')).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
    var vus = {}, sujets = (d && d.sujets ? d.sujets : []).filter(function (s) {
      var k = (s.theme || s.section || s.titre || '').trim().toLowerCase();
      if (!k || vus[k]) return false; vus[k] = true; return true;
    }).slice(0, 5);
    if (!sujets.length) return;
    zone.innerHTML = sujets.map(function (s) {
      var theme = s.theme || s.section || s.titre || '';
      var sujet = s.question || theme;
      return '<a class="chip chip-lien" href="/debat/?sujet=' + encodeURIComponent(sujet) + '&arene=1">' + DL.echapper(theme) + '</a>';
    }).join('');
    if (d.derniere_seance_lisible) maj.textContent = 'Dernière séance : ' + d.derniere_seance_lisible + ' · source : comptes rendus de l’Assemblée nationale';
    bandeau.hidden = false;
  }).catch(function () { /* bandeau reste masqué */ });
})();

/* Démo « En direct sur le plateau » : rejoue des Q/R enregistrées (data/demo_accueil.json), zéro réseau. */
(function () {
  'use strict';
  var bloc = document.getElementById('demo-live'), fenetre = document.getElementById('demo-fenetre');
  if (!bloc || !fenetre) return;
  var sequences = [], i = 0, minuterie = null, frappe = null;
  var reduit = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  /* Fichier statique produit par tools/demo_enregistrer.py — aucun backend requis. */
  fetch('/data/demo_accueil.json').then(function (r) { return r.ok ? r.json() : []; }).then(function (d) {
    sequences = Array.isArray(d) ? d : [];
    if (!sequences.length) return;
    bloc.hidden = false; i = Math.floor(Math.random() * sequences.length); jouer();
  }).catch(function () {});

  function jouer() {
    clearTimeout(minuterie); clearTimeout(frappe);
    var s = sequences[i % sequences.length]; i++;
    fenetre.innerHTML =
      '<div class="demo-entete"><img src="/img/candidats/' + DL.echapper(s.candidat_id) + '.webp" alt="" width="40" height="40"><div><strong>' + DL.echapper(s.nom) + '</strong><span class="meta"> · ' + DL.echapper(s.parti) + '</span></div>' +
      '<button type="button" class="lien-bouton demo-suivant">Autre exemple →</button></div>' +
      '<div class="msg msg-visiteur"><p>' + DL.echapper(s.question) + '</p></div>' +
      '<div class="msg msg-candidat"><div class="msg-corps"><p class="msg-attente">Consulte son programme…</p></div></div>' +
      '<p class="demo-cta"><a class="btn btn-secondaire btn-petit" href="/candidats/' + DL.echapper(s.candidat_id) + '/?q=' + encodeURIComponent(s.question) + '">Posez-lui la vôtre →</a></p>';
    fenetre.querySelector('.demo-suivant').addEventListener('click', jouer);
    var corps = fenetre.querySelector('.msg-corps'), texte = s.reponse || '', pos = 0;
    function html(t) { return '<p>' + DL.echapper(t).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>') + '</p>'; }
    function fin() { corps.innerHTML = html(texte) + DL.rendrePreuves(s.preuves || []); minuterie = setTimeout(jouer, 20000); }
    if (reduit) { fin(); return; }
    frappe = setTimeout(function pas() {
      pos = Math.min(texte.length, pos + 3 + Math.floor(Math.random() * 3));
      corps.innerHTML = html(texte.slice(0, pos));
      if (pos < texte.length) frappe = setTimeout(pas, 28); else fin();
    }, 700);
  }
})();

/* Duel de l'accueil : deux candidats tirés au sort, changement toutes les 9 s ; sujet = 1er thème Assemblée si disponible. */
(function () {
  'use strict';
  var src = document.getElementById('duel-data'), duel = document.getElementById('duel'); if (!src || !duel) return;
  var cands = src.textContent.split('\n').map(function (l) { var p = l.trim().split('|'); return p.length >= 4 ? { id: p[0], nom: p[1], parti: p[2], photo: p[3] } : null; }).filter(Boolean);
  if (cands.length < 2) return;
  var reduit = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function tirer() {
    var a = cands[Math.floor(Math.random() * cands.length)], b; do { b = cands[Math.floor(Math.random() * cands.length)]; } while (b === a);
    [['a', a], ['b', b]].forEach(function (x) {
      document.getElementById('duel-img-' + x[0]).src = x[1].photo; document.getElementById('duel-nom-' + x[0]).textContent = x[1].nom; document.getElementById('duel-parti-' + x[0]).textContent = x[1].parti;
    });
    var sujet = duel.getAttribute('data-sujet') || '';
    duel.href = '/debat/?arene=1&candidats=' + encodeURIComponent(a.id + ',' + b.id) + (sujet ? '&sujet=' + encodeURIComponent(sujet) : '');
  }
  tirer(); if (!reduit) setInterval(tirer, 9000);
  /* sujet du jour : premier thème Assemblée chargé par le bandeau */
  var obs = new MutationObserver(function () {
    var chip = document.querySelector('#assemblee-themes .chip'); if (!chip) return;
    var q = decodeURIComponent((chip.getAttribute('href') || '').split('sujet=')[1] || '').split('&')[0];
    if (q) { duel.setAttribute('data-sujet', q); document.getElementById('duel-sujet').textContent = 'Sujet du jour : ' + chip.textContent; tirer(); }
    obs.disconnect();
  });
  var zone = document.getElementById('assemblee-themes'); if (zone) obs.observe(zone, { childList: true });
})();
