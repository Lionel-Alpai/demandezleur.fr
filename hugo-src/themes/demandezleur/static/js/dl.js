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
