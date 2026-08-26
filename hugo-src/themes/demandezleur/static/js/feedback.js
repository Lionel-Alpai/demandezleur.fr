(function() {
    'use strict';
    
    const $form = document.getElementById('feedback-form');
    const $textarea = document.getElementById('feedback-message');
    const $counter = document.getElementById('feedback-chars');
    const $submit = document.getElementById('feedback-submit');
    const $result = document.getElementById('feedback-result');
    
    if (!$form || !$textarea) return;
    
    // Compteur de caractères et activation du bouton
    function updateCounter() {
        const length = $textarea.value.trim().length;
        $counter.textContent = length;
        $submit.disabled = length < 10;
    }
    
    $textarea.addEventListener('input', updateCounter);
    
    // Soumission
    $form.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const message = $textarea.value.trim();
        if (message.length < 10) return;
        
        $submit.disabled = true;
        $submit.textContent = 'Envoi en cours...';
        $result.hidden = true;
        
        try {
            // Déduction de l'URL du backend en fonction de là où on se trouve (localhost ou IP locale)
            const apiUrl = (window.DL_API || '/api') + '/feedback';

            const response = await fetch(apiUrl, {
                method: 'POST',
                headers: DL.entetes({ 'Content-Type': 'application/json' }),
                body: JSON.stringify({ message: message }),
            });
            
            const data = await response.json();
            
            if (response.ok) {
                $result.className = 'resultat success';
                $result.textContent = data.message || 'Merci pour votre retour.';
                $result.hidden = false;
                $textarea.value = '';
                updateCounter();
                $submit.textContent = 'Envoyer';
            } else {
                $result.className = 'resultat error';
                $result.textContent = (data.detail && data.detail.message) || 
                                      'Une erreur est survenue. Merci de réessayer.';
                $result.hidden = false;
                $submit.disabled = false;
                $submit.textContent = 'Envoyer';
            }
        } catch (e) {
            $result.className = 'resultat error';
            $result.textContent = 'Erreur réseau. Vérifiez votre connexion et réessayez.';
            $result.hidden = false;
            $submit.disabled = false;
            $submit.textContent = 'Envoyer';
        }
    });
    
    updateCounter();
})();
