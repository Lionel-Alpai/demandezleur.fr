/* debat-partage.js — rend un débat sauvegardé (/d/?id=…). Dépend de dl.js et export-image.js. */
(function () {
  'use strict';
  var $sujet = document.getElementById('partage-sujet'), $cont = document.getElementById('partage-container'), $meta = document.getElementById('partage-meta');
  var $actions = document.getElementById('partage-actions'), $mode = document.getElementById('partage-mode'), $sous = document.getElementById('partage-sous');
  if (!$sujet) return;
  var candidats = {};
  document.querySelectorAll('#candidats-data span').forEach(function (el) { candidats[el.dataset.id] = { id: el.dataset.id, nom: el.dataset.nom, parti_court: el.dataset.parti, famille: el.dataset.famille, photo: el.dataset.photo }; });
  var id = new URLSearchParams(window.location.search).get('id');
  if (!id) { $sujet.textContent = 'Aucun débat indiqué.'; $sous.textContent = ''; return; }
  DL.fetchJSON(DL.api('/debat/' + encodeURIComponent(id))).then(function (doc) {
    $sujet.textContent = doc.sujet; document.title = 'Débat : ' + doc.sujet + ' · demandezleur.fr';
    $mode.hidden = doc.mode !== 'arene';
    $cont.innerHTML = doc.candidats.map(function (cid) {
      var c = candidats[cid] || { nom: cid, parti_court: '', famille: '' }, tours = [];
      doc.tours.forEach(function (t) { t.interventions.forEach(function (i) { if (i.candidat_id === cid) tours.push({ t: t, i: i }); }); });
      return '<article class="recap-candidat famille-' + DL.echapper(c.famille) + '" style="--famille: var(--pastille)"><div class="recap-entete">' +
        (c.photo ? '<img src="' + DL.echapper(c.photo) + '" alt="">' : '') + '<div><strong>' + DL.echapper(c.nom) + '</strong><span class="meta"> · ' + DL.echapper(c.parti_court || c.parti || '') + '</span></div></div>' +
        tours.map(function (x) {
          var rev = x.i.revisions || [];
          return '<div class="recap-tour"><span class="meta">Tour ' + x.t.tour + (x.t.question_moderateur ? ' · question du modérateur : « ' + DL.echapper(x.t.question_moderateur) + ' »' : '') + '</span>' + DL.rendreTexteAnnote(x.i.texte, x.i.annotations) +
            DL.rendrePreuves(x.i.preuves || [], null, x.i.annotations) + (rev.length ? '<details class="revisions"><summary>' + rev.length + ' affirmation' + (rev.length > 1 ? 's' : '') + ' retirée' + (rev.length > 1 ? 's' : '') + ' par le garde-fou</summary><ul>' + rev.map(function (r) { return '<li>« ' + DL.echapper(r.phrase) + ' » — ' + DL.echapper(r.raison || '') + '</li>'; }).join('') + '</ul></details>' : '') + '</div>';
        }).join('') + '</article>';
    }).join('');
    $meta.textContent = 'Débat du ' + new Date(doc.cree_le).toLocaleString('fr-FR') + ' · ' + doc.tours.length + ' tour' + (doc.tours.length > 1 ? 's' : '') + ' · modèle ' + (doc.moteur || '') + ' · identifiant ' + doc.id;
    $actions.innerHTML = '<span class="recap-lien">' + DL.echapper(window.location.origin + '/d/?id=' + doc.id) + '</span><button type="button" class="btn btn-secondaire btn-petit" id="btn-copier">Copier le lien</button><button type="button" class="btn btn-secondaire btn-petit" id="btn-image">Exporter en image</button>';
    document.getElementById('btn-copier').addEventListener('click', function () { navigator.clipboard && navigator.clipboard.writeText(window.location.origin + '/d/?id=' + doc.id).then(function () { this.textContent = 'Copié ✓'; }.bind(this)); });
    document.getElementById('btn-image').addEventListener('click', function () { DL.exporterImage(doc, candidats); });
  }).catch(function (e) {
    $sujet.textContent = e.status === 404 ? 'Ce débat n’existe pas ou plus.' : 'Impossible de charger ce débat.'; $sous.textContent = '';
  });
})();
