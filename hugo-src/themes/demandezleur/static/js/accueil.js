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

/* Affiche de l'accueil : affrontements CHOISIS (data/affiches.json), rotation toutes les 8 s ; clic → Arène sur ce sujet. */
(function () {
  'use strict';
  var src = document.getElementById('duel-data'), aff = document.getElementById('affiches-data'), duel = document.getElementById('duel'); if (!src || !aff || !duel) return;
  var cands = {}; src.textContent.split('\n').forEach(function (l) { var p = l.trim().split('|'); if (p.length >= 4) cands[p[0]] = { id: p[0], nom: p[1], parti: p[2], photo: p[3] }; });
  var ta = document.createElement('textarea'), dec = function (t) { ta.innerHTML = t; return ta.value; };  /* Hugo encode les apostrophes (&#39;) dans ce bloc */
  var affiches = aff.textContent.split('\n').map(function (l) { var p = l.trim().split('|'); return p.length >= 4 && cands[p[0]] && cands[p[1]] ? { a: cands[p[0]], b: cands[p[1]], sujet: dec(p[2]), accroche: dec(p[3]) } : null; }).filter(Boolean);
  if (!affiches.length) return;
  /* Ordre : une affiche manuelle (poids lourds) d'abord, puis mélange aléatoire ; on évite le même candidat deux fois de suite. */
  var ordre = affiches.slice(1); for (var k = ordre.length - 1; k > 0; k--) { var j = Math.floor(Math.random() * (k + 1)); var t = ordre[k]; ordre[k] = ordre[j]; ordre[j] = t; }
  ordre.unshift(affiches[0]);
  for (var m = 1; m < ordre.length - 1; m++) { var prev = ordre[m - 1], cur = ordre[m]; if (cur.a === prev.a || cur.b === prev.b || cur.a === prev.b || cur.b === prev.a) { var n = m + 1; while (n < ordre.length && (ordre[n].a === prev.a || ordre[n].b === prev.b || ordre[n].a === prev.b || ordre[n].b === prev.a)) n++; if (n < ordre.length) { var tmp = ordre[m]; ordre[m] = ordre[n]; ordre[n] = tmp; } } }
  affiches = ordre;
  var i = 0, reduit = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  function montrer() {
    var x = affiches[i % affiches.length]; i++;
    if (x.sujet === '@assemblee') { var chip = document.querySelector('#assemblee-themes .chip'); x = { a: x.a, b: x.b, accroche: x.accroche, sujet: chip ? chip.textContent : 'ce qui s’est dit à l’Assemblée' }; }
    if (x.sujet === '@actu') { x = { a: x.a, b: x.b, accroche: x.accroche, sujet: (window.DL_actu && window.DL_actu[i % Math.max(1, window.DL_actu.length)]) || 'l’actualité de la semaine' }; }
    document.getElementById('duel-img-a').src = x.a.photo; document.getElementById('duel-img-b').src = x.b.photo;
    document.getElementById('duel-nom-a').textContent = x.a.nom.split(' ').slice(-1)[0] === 'Pen' ? 'Le Pen' : x.a.nom.split(' ').slice(-1)[0];
    document.getElementById('duel-nom-b').textContent = x.b.nom.split(' ').slice(-1)[0] === 'Pen' ? 'Le Pen' : x.b.nom.split(' ').slice(-1)[0];
    document.getElementById('duel-accroche').textContent = x.accroche || 'Arène';
    document.getElementById('duel-sujet').textContent = 'Sujet : ' + x.sujet;
    duel.href = '/debat/?arene=1&candidats=' + encodeURIComponent(x.a.id + ',' + x.b.id) + '&sujet=' + encodeURIComponent(x.sujet);
  }
  fetch(DL.api('/actu/sujets?n=6')).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) { window.DL_actu = (d && d.sujets || []).map(function (s) { return s.theme; }); }).catch(function () {});
  montrer(); if (!reduit) setInterval(montrer, 8000);
})();
