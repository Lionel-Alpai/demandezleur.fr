(function() {
  'use strict';
  
  // === État global du débat ===
  const state = {
    phase: 'setup',  // 'setup' | 'tour_en_cours' | 'fin_de_tour' | 'intervention' | 'recap'
    candidatsSelectionnes: [],  // array of candidat objects
    candidatsData: {},  // id -> candidat metadata (nom, parti, photo, couleur, famille)
    sujet: '',
    mode: 'standard',  // [parlement-ui]
    tour: 0,
    maxTours: 5,
    historique: [],  // liste des tours complets passés
    tourEnCours: {
      ordre: [],
      interventions: {},  // candidat_id -> texte accumulé
      position: 0,
    },
    eventSource: null,
  };
  
  // === Éléments DOM ===
  const $setup = document.getElementById('debat-setup');
  const $arena = document.getElementById('debat-arena');
  const $recap = document.getElementById('debat-recap');
  const $grid = document.getElementById('candidats-grid');
  const $counter = document.getElementById('counter-selected');
  const $sujetInput = document.getElementById('sujet-input');
  const $sujetChars = document.getElementById('sujet-chars');
  const $btnLaunch = document.getElementById('btn-launch');
  const $sujetDisplay = document.getElementById('sujet-display');
  const $tourDisplay = document.getElementById('tour-display');
  const $ordreListe = document.getElementById('ordre-liste');
  const $interventions = document.getElementById('debat-interventions');
  const $actions = document.getElementById('debat-actions');
  const $btnTourSuivant = document.getElementById('btn-tour-suivant');
  const $btnIntervenir = document.getElementById('btn-intervenir');
  const $btnFinDebat = document.getElementById('btn-fin-debat');
  const $interventionPanel = document.getElementById('intervention-panel');
  const $interventionInput = document.getElementById('intervention-input');
  const $interventionTargetBtns = document.getElementById('intervention-target-buttons');
  const $btnInterventionSubmit = document.getElementById('btn-intervention-submit');
  const $btnInterventionCancel = document.getElementById('btn-intervention-cancel');
  const $recapContainer = document.getElementById('recap-container');
  const $btnNouveauDebat = document.getElementById('btn-nouveau-debat');
  
  function afficherMessageBlocageDebat(detail) {
    const actionLabel = detail.action === 'debat_long' ? 'débats longs' : 'débats courts';
    const messageHTML = `
        <div class="rate-limit-blocage">
            <h3>Quota quotidien atteint</h3>
            <p>${detail.message}</p>
            <p class="limite-info">
                Vous avez utilisé votre quota de ${detail.limite} ${actionLabel} pour aujourd'hui.
            </p>
            <div class="rate-limit-soutien">
                <p class="petit" style="font-size:11px; color:rgba(255,255,255,0.4); margin-bottom:8px;">
                    Ce projet citoyen est développé bénévolement et son fonctionnement a un coût
                    en infrastructures et en API d'intelligence artificielle. Si vous souhaitez
                    soutenir son existence, vous pouvez contribuer librement sur notre
                    <a href="/soutenir/" style="color:var(--rouge-france); text-decoration:underline;">page de soutien</a>.
                </p>
                <p class="petit" style="font-size:10px; color:rgba(255,255,255,0.3); font-style:italic;">
                    Aucun don ne donne droit à un accès prioritaire : votre contribution
                    soutient le projet, pas votre propre usage.
                </p>
            </div>
            <button class="btn btn-secondary" onclick="location.href='/'" style="margin-top:20px; padding:8px 16px; background:rgba(255,255,255,0.05); border:1px solid var(--border-medium); color:var(--text-primary); cursor:pointer; border-radius:4px;">
                Retour à l'accueil
            </button>
        </div>
    `;
    
    // Masquer les sections débat et afficher le blocage
    $setup.style.display = 'none';
    $arena.style.display = 'none';
    if ($recap) {
        $recap.innerHTML = '<div id="recap-container"></div>'; // On vide pour le message
        const container = document.getElementById('recap-container');
        container.innerHTML = messageHTML;
        $recap.style.display = 'block';
    }
  }

  // === Init ===
  function init() {
    initSelection();
    initLaunch();
    initActions();
    initIntervention();
    initRecap();
    initParlement();  // [parlement-ui]
  }
  
  function initSelection() {
    if (!$grid) return;
    const cards = $grid.querySelectorAll('.candidat-select-card');
    
    cards.forEach(card => {
      const id = card.dataset.candidatId;
      state.candidatsData[id] = {
        id,
        nom: card.dataset.candidatNom,
        parti: card.dataset.candidatParti,
        famille: card.dataset.candidatFamille,
        couleur: card.dataset.candidatCouleur,
        photo: card.querySelector('img')?.src,
      };
      
      card.addEventListener('click', () => toggleSelection(id, card));
    });
    
    $sujetInput.addEventListener('input', () => {
      $sujetChars.textContent = $sujetInput.value.length;
      updateLaunchButton();
    });
  }

  function toggleSelection(id, card) {
    const index = state.candidatsSelectionnes.findIndex(c => c.id === id);
    
    if (index >= 0) {
      state.candidatsSelectionnes.splice(index, 1);
      card.classList.remove('selected');
    } else {
      if (state.candidatsSelectionnes.length >= 5) {
        return;
      }
      state.candidatsSelectionnes.push(state.candidatsData[id]);
      card.classList.add('selected');
    }
    
    $counter.textContent = state.candidatsSelectionnes.length;
    
    const cards = $grid.querySelectorAll('.candidat-select-card');
    if (state.candidatsSelectionnes.length >= 5) {
      cards.forEach(c => {
        if (!c.classList.contains('selected')) c.classList.add('disabled');
      });
    } else {
      cards.forEach(c => c.classList.remove('disabled'));
    }
    
    updateLaunchButton();
  }

  function updateLaunchButton() {
    const nbCandidats = state.candidatsSelectionnes.length;
    const sujet = $sujetInput.value.trim();
    $btnLaunch.disabled = !(nbCandidats >= 2 && nbCandidats <= 5 && sujet.length > 0);
  }

  function initLaunch() {
    if (!$btnLaunch) return;
    $btnLaunch.addEventListener('click', lancerDebat);
  }

  async function lancerDebat() {
    state.sujet = $sujetInput.value.trim();
    state.tour = 1;
    state.historique = [];
    
    $setup.style.display = 'none';
    $arena.style.display = 'block';
    $sujetDisplay.textContent = state.sujet;
    $tourDisplay.textContent = `${state.tour}/${state.maxTours}`;
    
    window.scrollTo({ top: 0, behavior: 'smooth' });
    await lancerTour('ouverture');
  }

  async function lancerTour(typeTour, options = {}) {
    state.phase = 'tour_en_cours';
    state.tourEnCours = {
      ordre: [],
      interventions: {},
      position: 0,
    };
    
    $actions.style.display = 'none';
    $interventions.innerHTML = '';
    
    const payload = {
      candidats: state.candidatsSelectionnes.map(c => c.id),
      sujet: state.sujet,
      tour: state.tour,
      type_tour: typeTour,
      historique: state.historique,
      mode: state.mode,  // [parlement-ui]
    };
    
    if (typeTour === 'intervention') {
      payload.question_moderateur = options.question;
      payload.candidat_interpelle_id = options.candidatInterpelleId;
    }
    
    try {
      const apiUrl = (window.DL_API || '/api') + '/debat/stream';

      const response = await fetch(apiUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      
      if (response.status === 429) {
        const data = await response.json();
        afficherMessageBlocageDebat(data.detail);
        return;
      }

      if (!response.ok) {
        throw new Error('Erreur réseau : ' + response.status);
      }
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';
      
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        
        buffer += decoder.decode(value, { stream: true });
        
        const events = buffer.split('\n\n');
        buffer = events.pop();
        
        for (const event of events) {
          const line = event.trim();
          if (!line.startsWith('data: ')) continue;
          try {
            const data = JSON.parse(line.substring(6));
            handleStreamEvent(data, options);
          } catch (e) {
            console.error('Parse SSE error:', e, line);
          }
        }
      }
    } catch (e) {
      console.error('Erreur débat stream:', e);
      alert('Erreur technique pendant le débat. Vérifiez que l\'API est lancée.');
      finDeTour({interventions_complete: []}); 
    }
  }

  function handleStreamEvent(data, options) {
    switch (data.type) {
      case 'turn_start':
        state.tourEnCours.ordre = data.candidats_ordre;
        afficherOrdre(data.candidats_meta);
        creerCartesInterventions(data.candidats_ordre, options);
        break;
      
      case 'speaker_start':
        marquerCandidatSpeaking(data.candidat_id);
        state.tourEnCours.interventions[data.candidat_id] = '';
        break;
      
      case 'token':
        state.tourEnCours.interventions[data.candidat_id] += data.text;
        appendTextAuCandidat(data.candidat_id, data.text);
        break;
      
      case 'speaker_end':
        demarquerCandidatSpeaking(data.candidat_id);
        break;
      
      case 'turn_end':
        finDeTour(data);
        break;
      
      case 'error':
        console.error('Erreur candidat:', data);
        afficherErreurCandidat(data.candidat_id, data.error);
        break;
    }
  }

  function afficherOrdre(candidatsMeta) {
    $ordreListe.innerHTML = candidatsMeta.map((c, i) => 
      `<span style="color:var(--text-primary); font-weight:500;">${i + 1}. ${c.nom}</span>`
    ).join(' <span style="opacity:0.3; margin:0 4px;">→</span> ');
  }

  function creerCartesInterventions(ordreIds, options) {
    $interventions.innerHTML = '';
    ordreIds.forEach(id => {
      const candidat = state.candidatsData[id];
      const card = document.createElement('div');
      card.className = 'intervention-card';
      card.id = `intervention-${id}`;
      card.style.setProperty('--candidat-couleur', candidat.couleur);
      
      const badgeInterpelle = options.candidatInterpelleId === id 
        ? '<span class="intervention-badge-interpelle">Interpellé</span>' 
        : '';
      
      card.innerHTML = `
        <div class="intervention-header">
          ${candidat.photo ? `<img class="intervention-avatar" src="${candidat.photo}" alt="${candidat.nom}">` : ''}
          <div>
            <div class="intervention-nom">${candidat.nom}${badgeInterpelle}</div>
            <div class="intervention-parti">${candidat.parti}</div>
          </div>
        </div>
        <div class="intervention-texte" id="texte-${id}"></div>
      `;
      $interventions.appendChild(card);
    });
  }

  function marquerCandidatSpeaking(candidatId) {
    const card = document.getElementById(`intervention-${candidatId}`);
    if (card) {
      card.classList.add('speaking');
      card.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  function demarquerCandidatSpeaking(candidatId) {
    const card = document.getElementById(`intervention-${candidatId}`);
    if (card) card.classList.remove('speaking');
  }

  function appendTextAuCandidat(candidatId, text) {
    const $texte = document.getElementById(`texte-${candidatId}`);
    if ($texte) {
        $texte.textContent += text;
        // Auto-scroll smooth while typing
        const card = document.getElementById(`intervention-${candidatId}`);
        if (card) card.scrollIntoView({ behavior: 'auto', block: 'nearest' });
    }
  }

  function afficherErreurCandidat(candidatId, erreur) {
    const $texte = document.getElementById(`texte-${candidatId}`);
    if ($texte) {
      $texte.textContent = `(Erreur technique : ${erreur})`;
      $texte.style.color = 'rgba(237,41,57,0.8)';
    }
  }

  function finDeTour(data) {
    state.phase = 'fin_de_tour';
    
    state.historique.push({
      tour: state.tour,
      type: state.tourEnCours.typeTour || 'normal',
      question_moderateur: state.tourEnCours.question,
      candidat_interpelle_nom: state.tourEnCours.candidatInterpelleNom,
      interventions: data.interventions_complete,
    });
    
    if (state.tour >= state.maxTours) {
      $actions.innerHTML = `
        <button class="btn btn-debat-action btn-end" id="btn-fin-debat-final" style="grid-column: 1 / -1; width: 100%;">
          <span class="btn-icon">■</span>
          <span class="btn-label">Fin du débat (limite de 5 tours atteinte)</span>
        </button>
      `;
      document.getElementById('btn-fin-debat-final').addEventListener('click', afficherRecap);
    }
    
    $actions.style.display = 'grid';
  }

  function initActions() {
    if (!$btnTourSuivant) return;
    
    $btnTourSuivant.addEventListener('click', () => {
      state.tour++;
      $tourDisplay.textContent = `${state.tour}/${state.maxTours}`;
      lancerTour('tour_suivant');
    });
    
    $btnIntervenir.addEventListener('click', () => {
      ouvrirPanneauIntervention();
    });
    
    $btnFinDebat.addEventListener('click', afficherRecap);
  }

  function initIntervention() {
    if (!$interventionInput) return;
    $interventionInput.addEventListener('input', updateInterventionSubmit);
    $btnInterventionCancel.addEventListener('click', fermerPanneauIntervention);
    $btnInterventionSubmit.addEventListener('click', soumettreIntervention);
  }

  let candidatInterpelleSelectionne = null;

  function ouvrirPanneauIntervention() {
    candidatInterpelleSelectionne = null;
    $interventionInput.value = '';
    
    $interventionTargetBtns.innerHTML = '';
    state.candidatsSelectionnes.forEach(candidat => {
      const btn = document.createElement('button');
      btn.className = 'btn-target';
      btn.textContent = candidat.nom;
      btn.dataset.candidatId = candidat.id;
      btn.addEventListener('click', () => {
        document.querySelectorAll('.btn-target').forEach(b => b.classList.remove('selected'));
        btn.classList.add('selected');
        candidatInterpelleSelectionne = candidat.id;
        updateInterventionSubmit();
      });
      $interventionTargetBtns.appendChild(btn);
    });
    
    $actions.style.display = 'none';
    $interventionPanel.style.display = 'block';
    $interventionPanel.scrollIntoView({ behavior: 'smooth' });
  }

  function updateInterventionSubmit() {
    const question = $interventionInput.value.trim();
    $btnInterventionSubmit.disabled = !(question.length > 0 && candidatInterpelleSelectionne);
  }

  function fermerPanneauIntervention() {
    $interventionPanel.style.display = 'none';
    $actions.style.display = 'grid';
  }

  function soumettreIntervention() {
    const question = $interventionInput.value.trim();
    const candidatId = candidatInterpelleSelectionne;
    const candidatNom = state.candidatsData[candidatId].nom;
    
    state.tourEnCours.typeTour = 'intervention';
    state.tourEnCours.question = question;
    state.tourEnCours.candidatInterpelleNom = candidatNom;

    $interventionPanel.style.display = 'none';
    state.tour++;
    $tourDisplay.textContent = `${state.tour}/${state.maxTours}`;
    
    lancerTour('intervention', {
      question,
      candidatInterpelleId: candidatId,
    });
  }

  function initRecap() {
    if (!$btnNouveauDebat) return;
    $btnNouveauDebat.addEventListener('click', resetDebat);
  }

  function afficherRecap() {
    state.phase = 'recap';
    $arena.style.display = 'none';
    $recap.style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    const parCandidat = {};
    state.candidatsSelectionnes.forEach(c => {
      parCandidat[c.id] = { candidat: c, interventions: [] };
    });
    state.historique.forEach(tour => {
      tour.interventions.forEach(i => {
        if (parCandidat[i.candidat_id]) {
          parCandidat[i.candidat_id].interventions.push(i.texte);
        }
      });
    });
    
    $recapContainer.innerHTML = '';
    Object.values(parCandidat).forEach(({ candidat, interventions }) => {
      const div = document.createElement('div');
      div.className = 'recap-candidat';
      div.style.setProperty('--candidat-couleur', candidat.couleur);
      div.innerHTML = `
        <div class="recap-header">
          ${candidat.photo ? `<img src="${candidat.photo}" alt="${candidat.nom}">` : ''}
          <div>
            <div class="recap-nom">${candidat.nom}</div>
            <div class="recap-parti">${candidat.parti}</div>
          </div>
        </div>
        <div class="recap-positions">
          ${interventions.map((t, i) => `<p><strong>Tour ${i + 1} :</strong> ${t}</p>`).join('')}
        </div>
      `;
      $recapContainer.appendChild(div);
    });
  }

  // [parlement-ui] début
  function urlSujetsParlement() {
    // [parlement-ui] même convention d'URL que le reste du fichier
    return (window.DL_API || '/api') + '/parlement/sujets';
  }

  function echapper(s) {
    // [parlement-ui] données d'API injectées en innerHTML : on échappe tout
    if (s === null || s === undefined) return '';
    return String(s)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function tronquerParlement(texte, taille) {
    // [parlement-ui]
    const brut = (texte === null || texte === undefined) ? '' : String(texte).trim();
    if (brut.length <= taille) return brut;
    return brut.slice(0, taille).trim() + '…';
  }

  function gabaritSujetParlement(sujet) {
    // [parlement-ui] chaîne vide si le sujet n'a rien d'exploitable
    if (!sujet) return '';
    const section = (sujet.section === null || sujet.section === undefined) ? '' : String(sujet.section).trim();
    const titre = (sujet.titre === null || sujet.titre === undefined) ? '' : String(sujet.titre).trim();
    const repris = section !== '' ? section : titre;
    if (repris === '') return '';
    const affiche = titre !== '' ? titre : section;
    const meta = [];
    if (sujet.date_lisible) meta.push(echapper(String(sujet.date_lisible).trim()));
    if (sujet.orateur) meta.push(echapper(String(sujet.orateur).trim()));
    const extrait = tronquerParlement(sujet.extrait, 160);
    let html = '<button type="button" class="parlement-sujet" data-sujet="' + echapper(repris) + '"';
    html += ' style="display:block; width:100%; text-align:left; cursor:pointer; margin-bottom:8px;';
    html += ' padding:10px 12px; border:1px solid var(--border-subtle);';
    html += ' background:rgba(255,255,255,0.03); color:var(--text-secondary);';
    html += ' font-family:inherit; font-size:12px; line-height:1.6;">';
    html += '<span style="display:block; color:var(--text-primary);">' + echapper(affiche) + '</span>';
    if (meta.length) {
      html += '<span style="display:block; margin-top:4px; font-family:monospace; font-size:10px;';
      html += ' text-transform:uppercase; letter-spacing:1px; color:var(--text-tertiary);">';
      html += meta.join(' · ') + '</span>';
    }
    if (extrait !== '') {
      html += '<span style="display:block; margin-top:6px; color:var(--text-secondary);">' + echapper(extrait) + '</span>';
    }
    if (sujet.url) {
      html += '<a class="parlement-lien" href="' + echapper(String(sujet.url).trim()) + '" target="_blank" rel="noopener"';
      html += ' style="display:inline-block; margin-top:6px; font-family:monospace; font-size:10px;';
      html += ' text-transform:uppercase; letter-spacing:1px; color:var(--rouge-france); text-decoration:none;">compte rendu</a>';
    }
    html += '</button>';
    return html;
  }

  function brancherSujetsParlement(conteneur) {
    // [parlement-ui] un clic arme le champ sujet, sans appeler l'existant
    const boutons = conteneur.querySelectorAll('.parlement-sujet');
    Array.prototype.forEach.call(boutons, function(bouton) {
      bouton.addEventListener('click', function() {
        const champ = document.getElementById('sujet-input');
        if (!champ) return;
        const texte = bouton.getAttribute('data-sujet') || '';
        if (texte === '') return;
        champ.value = texte;
        champ.dispatchEvent(new Event('input', { bubbles: true }));
        Array.prototype.forEach.call(boutons, function(autre) {
          autre.classList.remove('selectionne');
        });
        bouton.classList.add('selectionne');
        if (typeof champ.focus === 'function') champ.focus();
      });
    });
    const liens = conteneur.querySelectorAll('.parlement-lien');
    Array.prototype.forEach.call(liens, function(lien) {
      lien.addEventListener('click', function(event) {
        event.stopPropagation();  // [parlement-ui] le lien ne remplit pas le champ
      });
    });
  }

  function chargerSujetsParlement() {
    // [parlement-ui] en cas d'échec : rien affiché, le bandeau reste masqué
    const bandeau = document.getElementById('parlement-bandeau');
    const conteneur = document.getElementById('parlement-sujets');
    if (!bandeau || !conteneur) return;
    fetch(urlSujetsParlement())
      .then(function(reponse) {
        if (!reponse || !reponse.ok) {
          throw new Error('parlement: statut ' + (reponse ? reponse.status : 'inconnu'));
        }
        return reponse.json();
      })
      .then(function(donnees) {
        if (!donnees || !Array.isArray(donnees.sujets) || donnees.sujets.length === 0) return;
        const sujets = donnees.sujets.slice(0, 6);
        const morceaux = [];
        sujets.forEach(function(sujet) {
          const html = gabaritSujetParlement(sujet);
          if (html !== '') morceaux.push(html);
        });
        if (morceaux.length === 0) return;
        conteneur.innerHTML = morceaux.join('');
        brancherSujetsParlement(conteneur);
        const maj = document.getElementById('parlement-maj');
        if (maj && donnees.derniere_seance_lisible) {
          maj.textContent = 'dernière séance : ' + donnees.derniere_seance_lisible;
        }
        bandeau.style.display = 'block';
      })
      .catch(function(erreur) {
        console.warn('[parlement-ui] sujets parlementaires indisponibles', erreur);
      });
  }

  function synchroniserModeArene() {
    // [parlement-ui]
    const bascule = document.getElementById('mode-arene');
    if (!bascule) return;
    state.mode = bascule.checked ? 'arene' : 'standard';
    const avert = document.getElementById('arene-avertissement');
    if (avert) avert.style.display = bascule.checked ? 'block' : 'none';
  }

  function initParlement() {
    // [parlement-ui] appelé par init() ; tolère un gabarit plus ancien
    const bascule = document.getElementById('mode-arene');
    if (bascule) {
      bascule.addEventListener('change', synchroniserModeArene);
      bascule.addEventListener('click', synchroniserModeArene);
      synchroniserModeArene();
    }
    chargerSujetsParlement();
  }
  // [parlement-ui] fin
  function resetDebat() {
    state.phase = 'setup';
    state.candidatsSelectionnes = [];
    state.sujet = '';
    state.tour = 0;
    state.historique = [];
    
    $recap.style.display = 'none';
    $arena.style.display = 'none';
    $setup.style.display = 'block';
    window.scrollTo({ top: 0, behavior: 'smooth' });
    
    document.querySelectorAll('.candidat-select-card').forEach(c => {
      c.classList.remove('selected', 'disabled');
    });
    $sujetInput.value = '';
    $sujetChars.textContent = '0';
    $counter.textContent = '0';
    $btnLaunch.disabled = true;
    // [parlement-ui] retour au mode standard
    state.mode = 'standard';
    const basculeAreneReset = document.getElementById('mode-arene');
    if (basculeAreneReset) basculeAreneReset.checked = false;
    const avertAreneReset = document.getElementById('arene-avertissement');
    if (avertAreneReset) avertAreneReset.style.display = 'none';
  }
  
  init();
})();
