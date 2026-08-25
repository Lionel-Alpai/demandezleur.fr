/* chat.js — chat d'une fiche candidat : preuves, chips, historique, quota. Dépend de dl.js. */
(function () {
  'use strict';
  var form = document.getElementById('chatFormFull'); if (!form) return;
  var input = document.getElementById('chatInputFull'), bouton = document.getElementById('chatSendFull');
  var fenetre = document.getElementById('chatWindow'), chips = document.getElementById('chat-chips');
  var candidatId = form.dataset.candidat, historique = [], enCours = false;

  var params = new URLSearchParams(window.location.search), q = params.get('q');
  if (q) { input.value = q; window.history.replaceState({}, document.title, window.location.pathname); envoyer(); }

  form.addEventListener('submit', function (e) { e.preventDefault(); envoyer(); });
  if (chips) chips.addEventListener('click', function (e) {
    var b = e.target.closest('[data-question]'); if (!b || enCours) return;
    input.value = b.getAttribute('data-question'); envoyer();
  });

  function ajouter(role, html) {
    var el = document.createElement('div'); el.className = 'msg msg-' + role; el.innerHTML = html;
    fenetre.appendChild(el); fenetre.scrollTop = fenetre.scrollHeight; return el;
  }
  function occupe(b) { enCours = b; input.disabled = b; bouton.disabled = b; if (!b) input.focus(); }
  function texteHTML(t) { return DL.echapper(t).replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>').replace(/\n\n/g, '</p><p>').replace(/\n/g, '<br>'); }

  function envoyer() {
    var texte = input.value.trim(); if (!texte || enCours) return;
    ajouter('visiteur', '<p>' + DL.echapper(texte) + '</p>');
    input.value = ''; occupe(true);
    var rep = ajouter('candidat', '<p class="msg-attente">Consulte son programme…</p>');
    var corps = document.createElement('div'); corps.className = 'msg-corps';
    var complet = '', preuvesHTML = '';

    fetch(DL.api('/ask'), {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ candidat_id: candidatId, question: texte, history: historique })
    }).then(function (r) {
      if (r.status === 429) return r.json().then(function (d) { rep.remove(); blocage(d.detail); occupe(false); });
      if (!r.ok) throw new Error('HTTP ' + r.status);
      rep.innerHTML = ''; rep.appendChild(corps);
      return DL.lireSSE(r, function (ev) {
        if (ev.type === 'preuves') { preuvesHTML = DL.rendrePreuves(ev.preuves || []); }
        else if (ev.type === 'token') { complet += ev.text || ''; corps.innerHTML = '<p>' + texteHTML(complet) + '</p>'; fenetre.scrollTop = fenetre.scrollHeight; }
        else if (ev.type === 'done') { terminer(); }
        else if (ev.type === 'error') { corps.innerHTML += '<p class="msg-erreur">Erreur : ' + DL.echapper(ev.error || 'inconnue') + '</p>'; occupe(false); }
      }).then(function () { if (enCours) terminer(); });
    }).catch(function () {
      rep.innerHTML = '<p class="msg-erreur">Serveur injoignable. Réessayez dans un instant.</p>'; occupe(false);
    });

    function terminer() {
      if (!enCours) return;
      corps.innerHTML = '<p>' + texteHTML(complet) + '</p>' + preuvesHTML +
        '<div class="msg-actions"><button type="button" class="lien-bouton" data-copier>Copier la réponse</button></div>';
      corps.querySelector('[data-copier]').addEventListener('click', function () {
        navigator.clipboard && navigator.clipboard.writeText(complet).then(function () { this.textContent = 'Copié ✓'; }.bind(this));
      });
      historique.push({ role: 'user', content: texte }, { role: 'assistant', content: complet });
      if (historique.length > 6) historique = historique.slice(-6);
      fenetre.scrollTop = fenetre.scrollHeight; occupe(false);
    }
  }

  function blocage(detail) {
    ajouter('systeme', '<div class="rate-limit-blocage"><h3>Quota quotidien atteint</h3><p>' + DL.echapper(detail.message || '') +
      '</p><p class="limite-info">Limite : ' + DL.echapper(String(detail.limite || '')) + ' questions par jour et par adresse IP.</p>' +
      '<p class="petit">Ce site citoyen est développé bénévolement ; l’IA a un coût. <a href="/soutenir/">Soutenir le projet</a> — sans accès prioritaire pour personne.</p></div>');
  }
})();
