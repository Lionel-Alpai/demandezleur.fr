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
