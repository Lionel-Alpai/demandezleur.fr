/* debat.js — le plateau : préparation → arène (tours, interventions) → récapitulatif. Dépend de dl.js. */
(function () {
  'use strict';
  var $ = function (id) { return document.getElementById(id); };
  var $setup = $('debat-setup'), $arena = $('debat-arena'), $recap = $('debat-recap');
  if (!$setup) return;
  var $grid = $('candidats-grid'), $counter = $('counter-selected'), $sujet = $('sujet-input'), $sujetChars = $('sujet-chars'), $btnLaunch = $('btn-launch');
  var $sujetDisplay = $('sujet-display'), $tourDisplay = $('tour-display'), $modeDisplay = $('mode-display'), $ordre = $('ordre-liste');
  var $interventions = $('debat-interventions'), $actions = $('debat-actions');
  var $panel = $('intervention-panel'), $panelInput = $('intervention-input'), $panelCibles = $('intervention-target-buttons');
  var $panelOk = $('btn-intervention-submit'), $panelNon = $('btn-intervention-cancel');
  var $recapSujet = $('recap-sujet'), $recapContainer = $('recap-container'), $recapPartage = $('recap-partage');
  var $arene = $('mode-arene'), $standard = $('mode-standard'), $bandeau = $('parlement-bandeau'), $sujetsParlement = $('parlement-sujets'), $parlementMaj = $('parlement-maj');

  var MAX_TOURS = window.DL_MAX_TOURS || 5;
  var state = { phase: 'setup', selection: [], data: {}, sujet: '', mode: 'arene', tour: 0, historique: [], enCours: null, cible: null };

  /* ---------- Préparation ---------- */
  $grid.querySelectorAll('.carte-selection').forEach(function (carte) {
    var id = carte.dataset.candidatId;
    state.data[id] = { id: id, nom: carte.dataset.candidatNom, parti: carte.dataset.candidatParti, famille: carte.dataset.candidatFamille,
      photo: (carte.querySelector('img') || {}).getAttribute ? carte.querySelector('img').getAttribute('src') : '' };
    carte.addEventListener('click', function () { basculer(id, carte); });
    carte.addEventListener('keydown', function (e) { if (e.key === ' ' || e.key === 'Enter') { e.preventDefault(); basculer(id, carte); } });
  });
  function basculer(id, carte) {
    var i = state.selection.indexOf(id);
    if (i >= 0) { state.selection.splice(i, 1); carte.setAttribute('aria-checked', 'false'); }
    else { if (state.selection.length >= 5) return; state.selection.push(id); carte.setAttribute('aria-checked', 'true'); }
    $counter.textContent = state.selection.length;
    var plein = state.selection.length >= 5;
    $grid.querySelectorAll('.carte-selection').forEach(function (c) { c.classList.toggle('disabled', plein && c.getAttribute('aria-checked') !== 'true'); });
    majLancement();
  }
  var $barre = $('barre-mobile'), $barreBtn = $('btn-launch-mobile'), $barreN = $('barre-compteur');
  function majLancement() {
    var n = state.selection.length, ok = (n >= 2 && n <= 5 && $sujet.value.trim().length > 0);
    $btnLaunch.disabled = !ok;
    if ($barre) { $barre.hidden = n === 0; $barreBtn.disabled = !ok; $barreN.textContent = n + ' / 5' + (ok ? '' : (n < 2 ? ' · 2 minimum' : ($sujet.value.trim() ? '' : ' · sujet manquant'))); }
  }
  if ($barreBtn) $barreBtn.addEventListener('click', function () { $btnLaunch.click(); });
  $sujet.addEventListener('input', function () { $sujetChars.textContent = $sujet.value.length; majLancement(); });
  function majMode() { state.mode = ($standard && $standard.checked) ? 'standard' : 'arene'; var lib = state.mode === 'arene' ? "Ouvrir l'Arène" : 'Ouvrir le plateau'; $btnLaunch.textContent = lib; if ($barreBtn) $barreBtn.textContent = lib; }
  if ($arene) $arene.addEventListener('change', majMode); if ($standard) $standard.addEventListener('change', majMode);

  /* Préremplissage par l'URL : /debat/?sujet=…&candidats=a,b&arene=1 */
  var params = new URLSearchParams(window.location.search);
  if (params.get('sujet')) { $sujet.value = params.get('sujet').slice(0, 500); $sujetChars.textContent = $sujet.value.length; }
  if (params.get('arene') === '0' && $standard) { $standard.checked = true; } if ($arene) majMode();
  (params.get('candidats') || '').split(',').filter(Boolean).forEach(function (id) {
    var carte = $grid.querySelector('.carte-selection[data-candidat-id="' + id + '"]'); if (carte) basculer(id, carte);
  });
  majLancement();

  /* Bandeau Assemblée (thèmes lisibles) */
  if ($bandeau) fetch(DL.api('/parlement/sujets?n=6')).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
    var sujets = d && d.sujets ? d.sujets : []; if (!sujets.length) return;
    $sujetsParlement.innerHTML = sujets.map(function (s) {
      return '<button type="button" class="chip" data-sujet="' + DL.echapper(s.question || s.theme) + '" title="' + DL.echapper((s.date_lisible || '') + (s.orateur ? ' · ' + s.orateur : '')) + '">' + DL.echapper(s.theme) + '</button>';
    }).join('');
    $sujetsParlement.addEventListener('click', function (e) {
      var b = e.target.closest('.chip'); if (!b) return;
      $sujetsParlement.querySelectorAll('.chip').forEach(function (c) { c.classList.toggle('selectionne', c === b); });
      $sujet.value = b.getAttribute('data-sujet'); $sujet.dispatchEvent(new Event('input')); $sujet.focus();
    });
    if (d.derniere_seance_lisible) $parlementMaj.textContent = '— dernière séance : ' + d.derniere_seance_lisible;
    $bandeau.hidden = false;
  }).catch(function () {});

  $btnLaunch.addEventListener('click', function () {
    if ($barre) $barre.hidden = true;
    state.sujet = $sujet.value.trim(); state.tour = 1; state.historique = [];
    $setup.hidden = true; $arena.hidden = false;
    $sujetDisplay.textContent = state.sujet; $tourDisplay.textContent = state.tour + '/' + MAX_TOURS;
    $modeDisplay.hidden = state.mode !== 'arene';
    window.scrollTo({ top: 0, behavior: 'smooth' });
    lancerTour('ouverture', {});
  });

  /* ---------- Tour ---------- */
  function lancerTour(typeTour, options) {
    state.phase = 'tour_en_cours';
    state.enCours = { type: typeTour, question: options.question, cibleId: options.cibleId, textes: {}, preuves: {}, revisions: {}, annotations: {} };
    $actions.hidden = true; $interventions.innerHTML = '';
    var payload = { candidats: state.selection.slice(), sujet: state.sujet, tour: state.tour, type_tour: typeTour, historique: state.historique, mode: state.mode };
    if (typeTour === 'intervention') { payload.question_moderateur = options.question; payload.candidat_interpelle_id = options.cibleId; }
    fetch(DL.api('/debat/stream'), { method: 'POST', headers: DL.entetes({ 'Content-Type': 'application/json' }), body: JSON.stringify(payload) })
      .then(function (r) {
        if (r.status === 429) return r.json().then(function (d) { blocage(d.detail); });
        if (!r.ok) throw new Error('HTTP ' + r.status);
        return DL.lireSSE(r, evenement);
      })
      .catch(function (e) {
        $interventions.insertAdjacentHTML('beforeend', '<p class="replique-erreur">Le plateau est injoignable (' + DL.echapper(e.message) + '). Réessayez dans un instant.</p>');
        finDeTour({ interventions_complete: [] });
      });
  }

  function evenement(ev) {
    var c = state.enCours;
    switch (ev.type) {
      case 'turn_start':
        $ordre.textContent = ev.candidats_meta.map(function (m, i) { return (i + 1) + '. ' + m.nom; }).join('  →  ');
        ev.candidats_meta.forEach(function (m) { if (m.photo) state.data[m.id].photo = m.photo; if (m.famille) state.data[m.id].famille = m.famille; });
        var strip = document.getElementById('plateau-strip');
        if (strip) strip.innerHTML = ev.candidats_ordre.map(function (id) { var d = state.data[id]; return '<figure id="strip-' + id + '">' + (d.photo ? '<img src="' + DL.echapper(d.photo) + '" alt="">' : '') + '<figcaption class="bandeau-nom"><strong>' + DL.echapper(d.nom) + '</strong><span>' + DL.echapper(d.parti) + '</span></figcaption></figure>'; }).join('');
        ev.candidats_ordre.forEach(function (id) { $interventions.appendChild(carteReplique(id, c.cibleId === id)); });
        break;
      case 'speaker_start':
        c.textes[ev.candidat_id] = '';
        var carte = $('replique-' + ev.candidat_id); if (carte) { carte.classList.add('parle'); carte.scrollIntoView({ behavior: 'smooth', block: 'center' }); }
        document.querySelectorAll('.plateau-strip figure').forEach(function (f) { f.classList.toggle('parle', f.id === 'strip-' + ev.candidat_id); });
        texteDe(ev.candidat_id).className = 'replique-texte attente';
        texteDe(ev.candidat_id).textContent = state.mode === 'arene' ? 'Vérifie ses pièces…' : 'Consulte son programme…';
        break;
      case 'preuves':
        c.preuves[ev.candidat_id] = ev.preuves || [];
        break;
      case 'token':
        var t = texteDe(ev.candidat_id);
        if (t.classList.contains('attente')) { t.className = 'replique-texte'; t.textContent = ''; }
        c.textes[ev.candidat_id] += ev.text || ''; t.textContent = c.textes[ev.candidat_id];
        break;
      case 'speaker_end':
        finReplique(ev);
        break;
      case 'turn_end':
        finDeTour(ev);
        break;
      case 'error':
        if (ev.candidat_id) { var te = texteDe(ev.candidat_id); te.className = 'replique-texte replique-erreur'; te.textContent = 'Ce candidat n’a pas pu répondre (' + (ev.error || 'erreur') + ').'; }
        else if (ev.code) { plateauFerme(ev); }
        break;
    }
  }
  function texteDe(id) { return $('texte-' + id); }
  function carteReplique(id, interpelle) {
    var d = state.data[id] || { nom: id, parti: '' };
    var el = document.createElement('article'); el.className = 'replique famille-' + (d.famille || ''); el.id = 'replique-' + id;
    el.style.setProperty('--famille', 'var(--pastille)');
    el.innerHTML = (d.photo ? '<img class="replique-avatar" src="' + DL.echapper(d.photo) + '" alt="">' : '<div class="replique-avatar"></div>') +
      '<div><div class="replique-entete"><span class="replique-nom">' + DL.echapper(d.nom) + '</span><span class="replique-parti">' + DL.echapper(d.parti) + '</span>' +
      (interpelle ? '<span class="badge-interpelle">Interpellé</span>' : '') + '<span class="replique-badges" id="badges-' + id + '"></span></div>' +
      '<div class="replique-texte" id="texte-' + id + '"></div><div class="replique-pied" id="pied-' + id + '"></div></div>';
    return el;
  }
  function finReplique(ev) {
    var id = ev.candidat_id, c = state.enCours, carte = $('replique-' + id);
    if (carte) carte.classList.remove('parle');
    c.revisions[id] = ev.revisions || []; c.annotations[id] = ev.annotations || [];
    if (ev.full_text) c.textes[id] = ev.full_text;
    var t = texteDe(id); t.className = 'replique-texte'; t.innerHTML = DL.rendreTexteAnnote(c.textes[id], c.annotations[id]);
    var pied = $('pied-' + id); if (pied) pied.innerHTML = DL.rendrePreuves(c.preuves[id] || [], libellePreuves(c.preuves[id] || [], c.annotations[id]), c.annotations[id]);
    var badges = $('badges-' + id), b = [];
    if (c.annotations[id].length) b.push('<span class="badge-annotation" title="Laissées dans le texte, marquées d’un astérisque">' + c.annotations[id].length + ' non étayée' + (c.annotations[id].length > 1 ? 's' : '') + '</span>');
    if (c.revisions[id].length) b.push('<span class="badge-revision">' + c.revisions[id].length + ' retirée' + (c.revisions[id].length > 1 ? 's' : '') + '</span>');
    if (badges) badges.innerHTML = b.join(' ');
    if (pied && c.revisions[id].length) pied.insertAdjacentHTML('beforeend', '<details class="revisions"><summary>Ce qui a été retiré, et pourquoi</summary><ul>' +
      c.revisions[id].map(function (r) { return '<li>« ' + DL.echapper(r.phrase) + ' » — ' + DL.echapper(r.raison || r.type) + '</li>'; }).join('') + '</ul></details>');
  }
  function libellePreuves(p, annotations) {
    var n = { programme: 0, piece: 0, adversaire: 0, dossier: 0, reproche: 0 }; p.forEach(function (x) { n[x.type] = (n[x.type] || 0) + 1; });
    var parts = [];
    if (annotations && annotations.length) parts.push(annotations.length + ' note' + (annotations.length > 1 ? 's' : '') + ' *');
    if (n.programme) parts.push(n.programme + ' extrait' + (n.programme > 1 ? 's' : '') + ' de son programme');
    if (n.piece) parts.push(n.piece + ' pièce Assemblée');
    if (n.adversaire) parts.push(n.adversaire + ' extrait' + (n.adversaire > 1 ? 's' : '') + ' du programme adverse');
    if (n.dossier) parts.push(n.dossier + ' fait' + (n.dossier > 1 ? 's' : '') + ' du dossier');
    if (n.reproche) parts.push(n.reproche + ' reproche' + (n.reproche > 1 ? 's' : '') + ' documenté' + (n.reproche > 1 ? 's' : ''));
    return 'Sur quoi il s’appuie : ' + (parts.join(' · ') || 'rien de précis');
  }
  function finDeTour(ev) {
    state.phase = 'fin_de_tour';
    var c = state.enCours;
    var interventions = (ev.interventions_complete || []).map(function (i) {
      return { candidat_id: i.candidat_id, candidat_nom: i.candidat_nom, texte: i.texte, preuves: i.preuves || c.preuves[i.candidat_id] || [], revisions: c.revisions[i.candidat_id] || [], annotations: i.annotations || c.annotations[i.candidat_id] || [] };
    });
    state.historique.push({ tour: state.tour, type: c.type, question_moderateur: c.question || null,
      candidat_interpelle_nom: c.cibleId ? state.data[c.cibleId].nom : null, candidat_interpelle_id: c.cibleId || null, interventions: interventions });
    if (state.tour >= MAX_TOURS) {
      $actions.innerHTML = '<button class="btn btn-accent" id="btn-fin-final">■ Clore le débat (' + MAX_TOURS + ' tours atteints)</button>';
      $('btn-fin-final').addEventListener('click', afficherRecap);
    }
    $actions.hidden = false;
  }

  /* ---------- Actions ---------- */
  $('btn-tour-suivant').addEventListener('click', function () { state.tour++; $tourDisplay.textContent = state.tour + '/' + MAX_TOURS; lancerTour('tour_suivant', {}); });
  $('btn-fin-debat').addEventListener('click', afficherRecap);
  $('btn-intervenir').addEventListener('click', function () {
    state.cible = null; $panelInput.value = ''; $panelOk.disabled = true;
    $panelCibles.innerHTML = state.selection.map(function (id) { return '<button type="button" class="chip" data-id="' + id + '">' + DL.echapper(state.data[id].nom) + '</button>'; }).join('');
    $actions.hidden = true; $panel.hidden = false; $panel.scrollIntoView({ behavior: 'smooth' }); $panelInput.focus();
  });
  $panelCibles.addEventListener('click', function (e) {
    var b = e.target.closest('.chip'); if (!b) return;
    $panelCibles.querySelectorAll('.chip').forEach(function (c) { c.classList.toggle('selectionne', c === b); });
    state.cible = b.getAttribute('data-id'); majPanel();
  });
  $panelInput.addEventListener('input', majPanel);
  function majPanel() { $panelOk.disabled = !($panelInput.value.trim() && state.cible); }
  $panelNon.addEventListener('click', function () { $panel.hidden = true; $actions.hidden = false; });
  $panelOk.addEventListener('click', function () {
    var q = $panelInput.value.trim(); if (!q || !state.cible) return;
    $panel.hidden = true; state.tour++; $tourDisplay.textContent = state.tour + '/' + MAX_TOURS;
    lancerTour('intervention', { question: q, cibleId: state.cible });
  });

  /* ---------- Récapitulatif ---------- */
  function afficherRecap() {
    state.phase = 'recap'; $arena.hidden = true; $recap.hidden = false; window.scrollTo({ top: 0, behavior: 'smooth' });
    $recapSujet.textContent = state.sujet;
    $recapContainer.innerHTML = state.selection.map(function (id) {
      var d = state.data[id], tours = [];
      state.historique.forEach(function (t) { t.interventions.forEach(function (i) { if (i.candidat_id === id) tours.push({ tour: t.tour, i: i, q: t.question_moderateur }); }); });
      return '<article class="recap-candidat famille-' + DL.echapper(d.famille || '') + '" style="--famille: var(--pastille)"><div class="recap-entete">' + (d.photo ? '<img src="' + DL.echapper(d.photo) + '" alt="">' : '') +
        '<div><strong>' + DL.echapper(d.nom) + '</strong><span class="meta"> · ' + DL.echapper(d.parti) + '</span></div></div>' +
        tours.map(function (x) { return '<div class="recap-tour"><span class="meta">Tour ' + x.tour + (x.q ? ' · question du modérateur : « ' + DL.echapper(x.q) + ' »' : '') + '</span>' + DL.rendreTexteAnnote(x.i.texte, x.i.annotations) + DL.rendrePreuves(x.i.preuves || [], libellePreuves(x.i.preuves || [], x.i.annotations), x.i.annotations) + '</div>'; }).join('') + '</article>';
    }).join('');
    $recapPartage.innerHTML = '<button type="button" class="btn btn-accent btn-petit" id="btn-lien">Obtenir un lien permanent</button><button type="button" class="btn btn-secondaire btn-petit" id="btn-export-texte">Exporter en texte</button><button type="button" class="btn btn-secondaire btn-petit" id="btn-export-image">Exporter en image</button><span class="meta" id="partage-etat"></span>';
    $('btn-export-texte').addEventListener('click', exporterTexte);
    $('btn-export-image').addEventListener('click', function () { DL.exporterImage(documentPartage(), dataPourImage()); });
    $('btn-lien').addEventListener('click', function () {
      var b = this, etat = $('partage-etat'); b.disabled = true; etat.textContent = 'Enregistrement…';
      DL.fetchJSON(DL.api('/debat/sauver'), { method: 'POST', headers: DL.entetes({ 'Content-Type': 'application/json' }), body: JSON.stringify(documentPartage()) })
        .then(function (r) {
          var url = window.location.origin + r.url; b.remove(); etat.textContent = '';
          $recapPartage.insertAdjacentHTML('afterbegin', '<span class="recap-lien" id="lien-permanent">' + DL.echapper(url) + '</span><button type="button" class="btn btn-secondaire btn-petit" id="btn-copier-lien">Copier</button><a class="btn btn-secondaire btn-petit" href="' + DL.echapper(r.url) + '" target="_blank" rel="noopener">Ouvrir ↗</a>');
          $('btn-copier-lien').addEventListener('click', function () { navigator.clipboard && navigator.clipboard.writeText(url).then(function () { this.textContent = 'Copié ✓'; }.bind(this)); });
          state.id = r.id;
        }).catch(function (e) { b.disabled = false; etat.textContent = e.status === 429 ? 'Quota de partages atteint pour aujourd’hui.' : 'Enregistrement impossible.'; });
    });
  }
  function documentPartage() {
    return { id: state.id || null, sujet: state.sujet, mode: state.mode, candidats: state.selection.slice(),
      tours: state.historique.map(function (t) { return { tour: t.tour, type: t.type, question_moderateur: t.question_moderateur, candidat_interpelle_id: t.candidat_interpelle_id,
        interventions: t.interventions.map(function (i) { return { candidat_id: i.candidat_id, texte: i.texte, preuves: i.preuves || [], revisions: i.revisions || [], annotations: i.annotations || [] }; }) }; }) };
  }
  function dataPourImage() { var d = {}; state.selection.forEach(function (id) { var c = state.data[id]; d[id] = { nom: c.nom, parti_court: c.parti, photo: c.photo }; }); return d; }
  function exporterTexte() {
    var lignes = ['Débat — ' + state.sujet + (state.mode === 'arene' ? ' (mode Arène)' : ''), 'demandezleur.fr — réponses générées par IA à partir des programmes officiels', ''];
    state.historique.forEach(function (t) {
      lignes.push('=== Tour ' + t.tour + (t.question_moderateur ? ' — modérateur : ' + t.question_moderateur : '') + ' ===');
      t.interventions.forEach(function (i) { lignes.push('[' + i.candidat_nom + '] ' + i.texte); if (i.preuves && i.preuves.length) lignes.push('  sources : ' + i.preuves.map(function (p) { return p.titre + (p.page ? ' (' + p.page + ')' : ''); }).join(' | ')); lignes.push(''); });
    });
    var blob = new Blob([lignes.join('\n')], { type: 'text/plain;charset=utf-8' }), a = document.createElement('a');
    a.href = URL.createObjectURL(blob); a.download = 'debat-demandezleur.txt'; document.body.appendChild(a); a.click(); a.remove();
  }
  $('btn-nouveau-debat').addEventListener('click', function () { window.location.href = '/debat/'; });

  function plateauFerme(ev) {
    $arena.hidden = true; $setup.hidden = true; $recap.hidden = false;
    $recapSujet.textContent = ev.code === 'budget' ? 'Plateau complet pour aujourd’hui' : (ev.code === 'en_cours' ? 'Un débat est déjà en cours' : 'Requête refusée');
    $recapContainer.innerHTML = '<div class="rate-limit-blocage"><p>' + DL.echapper(ev.error || '') + '</p>' +
      (ev.code === 'budget' ? '<p class="petit">Le site est financé bénévolement et l’IA a un coût ; un plafond quotidien protège son existence. La <a href="/">démo de l’accueil</a> et les débats partagés restent lisibles. <a href="/soutenir/">Soutenir le projet</a>.</p>' : '') + '</div>';
    $recapPartage.innerHTML = '';
  }
  function blocage(detail) {
    $arena.hidden = true; $setup.hidden = true; $recap.hidden = false;
    $recapSujet.textContent = 'Quota quotidien atteint';
    $recapContainer.innerHTML = '<div class="rate-limit-blocage"><p>' + DL.echapper(detail.message || '') + '</p><p class="limite-info">Limite : ' + DL.echapper(String(detail.limite || '')) + ' ' + (detail.action === 'debat_long' ? 'débats longs' : 'débats courts') + ' par jour et par adresse IP.</p><p class="petit">Ce site citoyen est développé bénévolement ; l’IA a un coût. <a href="/soutenir/">Soutenir le projet</a> — sans accès prioritaire pour personne.</p></div>';
    $recapPartage.innerHTML = '';
  }
  window.DL_debat = state;
})();
