(function (root) {
  'use strict';
  var THEMES = {
    'economie-travail': 'Économie et travail', 'ecologie-energie': 'Écologie et énergie',
    'social-sante': 'Social et santé', 'europe-international': 'Europe et international',
    'institutions': 'Institutions', 'education': 'Éducation',
    'securite-protection': 'Sécurité et protection', 'agriculture': 'Agriculture',
    'culture-numerique': 'Culture et numérique', 'immigration': 'Immigration',
    'services-publics': 'Services publics', 'logement': 'Logement',
    'vision-generale': 'Vision générale'
  };
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  function nb(n) { return (typeof n === 'number') ? n.toLocaleString('fr-FR') : esc(n); }
  function mesure(titre, m, unite) {
    if (!m) return '';
    var u = unite || '';
    return '<div class="cp-mesure"><h3>' + esc(titre) + '</h3>' +
      '<p class="cp-valeur">' + nb(m.valeur) + u + '</p>' +
      '<p class="cp-rang">Dans notre base, ce corpus est aujourd’hui au rang ' + nb(m.rang) +
      ' sur ' + nb(m.sur) + ' (médiane ' + nb(m.mediane) + u + ', maximum ' + nb(m.max) + u + ').</p></div>';
  }
  function rendreBilan(d) {
    var v = d.vue_qg || {};
    var h = '<h2>' + esc(d.nom) + (d.parti ? ' <small>(' + esc(d.parti) + ')</small>' : '') + '</h2>';
    h += '<p>Voici ce que notre recherche a trouvé. Nous avons pu manquer des documents : si vous en avez publié d’autres, aidez-nous à les intégrer.</p>';
    h += '<div class="cp-mesures">' +
      mesure('Volume du corpus (caractères)', v.volume_caracteres, '') +
      mesure('Part de documents de 2026-2027', v.fraicheur_2026_2027, ' %') +
      mesure('Part de documents officiels', v.officialite, ' %') +
      mesure('Thèmes couverts (sur 13)', v.couverture, '') + '</div>';
    var docs = d.documents || [];
    h += '<h2>Document par document</h2>';
    if (!docs.length) {
      h += '<p>Aucun document n’est aujourd’hui rattaché à ce candidat dans notre base.</p>';
    } else {
      h += '<table><thead><tr><th>Document</th><th>Année</th><th>Nature</th><th>Extraits</th><th>Thèmes</th></tr></thead><tbody>';
      docs.forEach(function (x) {
        var t = esc(x.titre || 'Document sans titre');
        if (x.url && /^https?:\/\//.test(x.url)) t = '<a href="' + esc(x.url) + '" rel="noopener nofollow">' + t + '</a>';
        var th = (x.themes || []).map(function (k) { return esc(THEMES[k] || k); }).join(', ');
        h += '<tr><td>' + t + '</td><td>' + esc(x.annee == null ? 'non datée' : x.annee) + '</td><td>' +
          esc(x.officialite || 'indéterminée') + '</td><td>' + nb(x.extraits) + '</td><td>' + th + '</td></tr>';
      });
      h += '</tbody></table>';
    }
    var trous = d.trous || [];
    h += '<h2>Thèmes que notre base ne couvre pas encore (' + trous.length + ' sur 13)</h2>';
    if (!trous.length) h += '<p>Les 13 thèmes sont couverts.</p>';
    else h += '<ul class="cp-trous">' + trous.map(function (k) { return '<li>' + esc(THEMES[k] || k) + '</li>'; }).join('') + '</ul>';
    var f = d.genere_le ? ('Bilan calculé le ' + esc(String(d.genere_le).slice(0, 10)) + ' à partir de la base telle qu’elle était ce jour-là.') : 'Date de calcul indisponible.';
    h += '<p class="cp-fraicheur">' + f + ' Il est recalculé à chaque ajout de document.</p>';
    return h;
  }
  root.DLCorpus = { rendreBilan: rendreBilan, esc: esc };
  if (typeof document === 'undefined' || !document.addEventListener) return;
  document.addEventListener('DOMContentLoaded', function () {
    var corps = document.getElementById('cp-corps');
    var neutre = document.getElementById('cp-neutre');
    if (!corps || !neutre) return;
    var j = new URLSearchParams(location.search).get('j') || '';
    function neutraliser() { corps.hidden = true; neutre.hidden = false; }
    if (!j) { neutraliser(); return; }
    var api = (root.DL_API || '/api') + '/qg/bilan?j=' + encodeURIComponent(j);
    fetch(api, { headers: { 'X-DL-Client': 'plateau' } }).then(function (r) {
      if (!r.ok) throw new Error('indisponible');
      return r.json();
    }).then(function (d) {
      corps.innerHTML = rendreBilan(d);
      corps.hidden = false; neutre.hidden = true;
      try { if (root.DLEnvoi) root.DLEnvoi.monter(j, d); } catch (e) { /* le bilan reste affiche */ }
      var t = document.getElementById('cp-titre'); if (t) t.textContent = 'Le bilan de votre corpus';
    }).catch(neutraliser);
  });
})(typeof window !== 'undefined' ? window : globalThis);
