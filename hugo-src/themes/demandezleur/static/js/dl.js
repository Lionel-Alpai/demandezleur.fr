/* dl.js — socle commun demandezleur.fr (menu, filtres, utilitaires). Sans dépendance. */
(function () {
  'use strict';
  var DL = window.DL = window.DL || {};
  DL.api = function (chemin) { return (window.DL_API || '/api') + chemin; };
  DL.echapper = function (s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
  };
  DL.fetchJSON = function (url, options) {
    return fetch(url, options).then(function (r) {
      if (!r.ok) { var e = new Error('HTTP ' + r.status); e.status = r.status; throw e; }
      return r.json();
    });
  };
  /* Lecture d'un flux SSE "data: {...}\n\n" → onEvent(objet) pour chaque ligne data. */
  DL.lireSSE = function (response, onEvent) {
    var lecteur = response.body.getReader(), dec = new TextDecoder(), tampon = '';
    function boucle() {
      return lecteur.read().then(function (r) {
        if (r.done) { if (tampon.trim()) traiter(tampon); return; }
        tampon += dec.decode(r.value, { stream: true });
        var parts = tampon.split('\n\n'); tampon = parts.pop();
        parts.forEach(traiter);
        return boucle();
      });
    }
    function traiter(bloc) {
      bloc.split('\n').forEach(function (ligne) {
        if (ligne.indexOf('data:') !== 0) return;
        var brut = ligne.slice(5).trim();
        if (!brut || brut === '[DONE]') return;
        try { onEvent(JSON.parse(brut)); } catch (e) { /* ligne ignorée */ }
      });
    }
    return boucle();
  };
  /* Texte d'une réplique avec les affirmations NON ÉTAYÉES marquées (atténuées + astérisque numéroté). */
  DL.rendreTexteAnnote = function (texte, annotations) {
    var t = String(texte || ''), notes = (annotations || []).filter(function (a) { return a && a.phrase; });
    if (!notes.length) return DL.echapper(t);
    var segments = [], reste = t, ordre = [];
    notes.forEach(function (a, k) {
      var ph = String(a.phrase).trim().replace(/[.!?…]+$/, ''), idx = reste.indexOf(ph);
      if (idx < 0) { var mots = ph.split(/\s+/).filter(function (m) { return m.length > 4; }).slice(0, 4); idx = mots.length ? reste.indexOf(mots[0]) : -1; ph = idx >= 0 ? reste.slice(idx, Math.min(reste.length, idx + Math.max(ph.length, 40))) : ''; }
      if (idx >= 0 && ph) ordre.push({ idx: idx, ph: ph, k: k });
    });
    ordre.sort(function (a, b) { return a.idx - b.idx; });
    var pos = 0, html = '';
    ordre.forEach(function (o) {
      if (o.idx < pos) return;
      html += DL.echapper(t.slice(pos, o.idx)) + '<span class="non-etayee" title="Affirmation non étayée par les pièces — voir note ' + (o.k + 1) + '">' + DL.echapper(o.ph) + '<sup class="asterisque">*' + (o.k + 1) + '</sup></span>';
      pos = o.idx + o.ph.length;
    });
    return html + DL.echapper(t.slice(pos));
  };
  /* Notes sous « Sur quoi il s'appuie » : ce qui n'est pas étayé, et pourquoi. */
  DL.rendreNotes = function (annotations) {
    var notes = (annotations || []).filter(function (a) { return a && a.phrase; });
    if (!notes.length) return '';
    return '<div class="notes-non-etayees"><p class="notes-titre">Affirmations non étayées par les pièces</p><ol>' + notes.map(function (a, k) {
      return '<li id="note-' + (k + 1) + '"><span class="asterisque">*' + (k + 1) + '</span> « ' + DL.echapper(a.phrase) + ' » — ' + DL.echapper(a.raison || 'aucune pièce fournie ne l’étaye') + '</li>';
    }).join('') + '</ol></div>';
  };
  /* Rendu du bloc « Sur quoi il s'appuie » */
  DL.rendrePreuves = function (preuves, titre, annotations) {
    if ((!preuves || !preuves.length) && !(annotations && annotations.length)) return '<p class="meta preuves-vide">Aucun extrait du programme ne correspondait précisément à cette question.</p>';
    preuves = preuves || [];
    var n = preuves.length, lib = { programme: 'Programme', piece: 'Assemblée', adversaire: 'Programme adverse', dossier: 'Dossier · fait vérifié', reproche: 'Reproche · ce que son camp dit de lui' };
    var html = '<details class="bloc-preuves"><summary>' + DL.echapper(titre || ('Sur quoi il s’appuie : ' + n + ' extrait' + (n > 1 ? 's' : ''))) + '</summary>';
    preuves.forEach(function (p) {
      html += '<div class="preuve preuve-' + DL.echapper(p.type || '') + '"><span class="preuve-type">' + DL.echapper(lib[p.type] || p.type) + '</span><span class="preuve-titre">' + DL.echapper(p.titre || '') + '</span>' +
        (p.page ? ' <span class="meta">· ' + DL.echapper(String(p.page)) + '</span>' : '') +
        (p.orateur ? ' <span class="meta">· ' + DL.echapper(p.orateur) + (p.date_lisible ? ', ' + DL.echapper(p.date_lisible) : '') + '</span>' : '') +
        (p.extrait ? '<p class="preuve-extrait">« ' + DL.echapper(p.extrait) + ' »</p>' : '') +
        (p.url ? '<a href="' + DL.echapper(p.url) + '" target="_blank" rel="noopener">' + (p.type === 'piece' ? 'Compte rendu officiel' : 'Source') + ' ↗</a>' : '') + '</div>';
    });
    return html + DL.rendreNotes(annotations) + '</details>';
  };
  /* Menu mobile */
  var btn = document.getElementById('menu-btn'), entete = document.getElementById('entete');
  if (btn && entete) {
    btn.addEventListener('click', function () {
      var ouvert = entete.classList.toggle('nav-ouvert');
      btn.setAttribute('aria-expanded', ouvert ? 'true' : 'false');
    });
  }
  /* Filtres par famille (liste des candidats) */
  var filtres = document.getElementById('filtres-famille');
  if (filtres) {
    filtres.addEventListener('click', function (ev) {
      var chip = ev.target.closest('.chip'); if (!chip) return;
      var fam = chip.getAttribute('data-famille') || '';
      filtres.querySelectorAll('.chip').forEach(function (c) { c.classList.toggle('selectionne', c === chip); });
      document.querySelectorAll('#grille-candidats .carte-candidat').forEach(function (carte) {
        carte.hidden = !!fam && carte.getAttribute('data-famille') !== fam;
      });
    });
  }
})();
