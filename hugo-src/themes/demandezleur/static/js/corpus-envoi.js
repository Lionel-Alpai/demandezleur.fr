(function (root) {
  'use strict';
  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  }
  var MAX = 10 * 1024 * 1024;
  var MESSAGES = {
    404: 'Ce lien n’est plus valable. Répondez au courrier qui vous l’a transmis.',
    413: 'Fichier trop volumineux (maximum 10 Mo).',
    415: 'Seuls les fichiers PDF sont acceptés.',
    429: 'Merci de patienter quelques secondes avant un nouvel envoi.'
  };
  function formulaireHtml(d) {
    return '<h2>Un document nous manque ? Envoyez-le</h2>' +
      '<p>Le document sera rattaché à votre corpus (' + esc(d.nom) + '). Chaque envoi est vérifié par la machine avant intégration.</p>' +
      '<form id="en-form" class="formulaire" enctype="multipart/form-data">' +
      '<div><label for="en-titre">Titre ou description du document</label>' +
      '<input type="text" id="en-titre" name="titre" maxlength="200" required></div>' +
      '<div><label for="en-url">Lien vers le document <span class="optionnel">(optionnel)</span></label>' +
      '<input type="url" id="en-url" name="url" placeholder="https://…"></div>' +
      '<div><label for="en-fichier">Fichier PDF <span class="optionnel">(optionnel — 10 Mo maximum)</span></label>' +
      '<input type="file" id="en-fichier" name="fichier" accept=".pdf,application/pdf"></div>' +
      '<div><label for="en-notes">Notes <span class="optionnel">(optionnel)</span></label>' +
      '<textarea id="en-notes" name="notes" rows="3" maxlength="1000"></textarea></div>' +
      '<button type="submit" id="en-submit" class="btn btn-accent">Envoyer le document</button>' +
      '</form><div id="en-result" class="resultat" hidden></div>';
  }
  function monter(jeton, d) {
    var sec = document.getElementById('cp-envoi');
    if (!sec) return;
    sec.innerHTML = formulaireHtml(d);
    sec.hidden = false;
    var form = document.getElementById('en-form');
    var res = document.getElementById('en-result');
    var btn = document.getElementById('en-submit');
    function dire(type, msg) { res.className = 'resultat ' + type; res.textContent = msg; res.hidden = false; }
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var f = document.getElementById('en-fichier').files[0];
      if (f && f.size > MAX) { dire('error', MESSAGES[413]); return; }
      var data = new FormData();
      data.append('jeton', jeton);
      data.append('candidat', d.slug || '');
      data.append('titre', document.getElementById('en-titre').value.trim());
      data.append('url', document.getElementById('en-url').value.trim());
      data.append('notes', document.getElementById('en-notes').value.trim());
      if (f) data.append('fichier', f);
      btn.disabled = true;
      fetch((root.DL_API || '/api') + '/suggerer-document', { method: 'POST', headers: { 'X-DL-Client': 'plateau' }, body: data })
        .then(function (r) {
          if (r.ok) { dire('success', 'Merci ! Votre document a bien été reçu. Il sera vérifié par la machine avant toute intégration.'); form.reset(); }
          else dire('error', MESSAGES[r.status] || 'Une erreur est survenue. Réessayez plus tard.');
        })
        .catch(function () { dire('error', 'Impossible de joindre le serveur. Vérifiez votre connexion.'); })
        .then(function () { btn.disabled = false; });
    });
  }
  root.DLEnvoi = { formulaireHtml: formulaireHtml, monter: monter, esc: esc };
})(typeof window !== 'undefined' ? window : globalThis);
