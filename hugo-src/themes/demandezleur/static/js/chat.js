document.addEventListener('DOMContentLoaded', function() {
  const form = document.getElementById('chatFormFull');
  const input = document.getElementById('chatInputFull');
  const windowEl = document.getElementById('chatWindow');
  
  if (!form) return;
  
  const candidatId = form.dataset.candidat;
  let history = [];

  // Check if there is a query param (e.g. redirected from homepage preview)
  const urlParams = new URLSearchParams(window.location.search);
  const initialQuery = urlParams.get('q');
  
  if (initialQuery) {
    input.value = initialQuery;
    handleSubmit(new Event('submit'));
    // clean url
    window.history.replaceState({}, document.title, window.location.pathname);
  }

  form.addEventListener('submit', handleSubmit);

  function handleSubmit(e) {
    if (e && e.preventDefault) e.preventDefault();
    
    const text = input.value.trim();
    if (!text) return;
    
    appendMessage('user', text);
    input.value = '';
    input.disabled = true;
    document.getElementById('chatSendFull').disabled = true;
    
    const placeholderMsg = appendMessage('assistant', '', true);
    
    // Déduction de l'URL du backend en fonction de là où on se trouve
    const apiUrl = window.location.port === '1313' 
      ? `http://${window.location.hostname}:8001/api/ask` 
      : '/api/ask';
    
    fetch(apiUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      body: JSON.stringify({
        candidat_id: candidatId,
        question: text,
        history: history
      })
    }).then(async response => {
      if (response.status === 429) {
        const data = await response.json();
        afficherMessageBlocage(data.detail);
        placeholderMsg.parentElement.remove(); // Remove the empty assistant placeholder
        input.disabled = false;
        document.getElementById('chatSendFull').disabled = false;
        return;
      }

      if (!response.ok) throw new Error("Erreur serveur");
      
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let fullResponse = "";
      
      while (true) {
        const {value, done} = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value, {stream: true});
        const lines = chunk.split('\n');
        
        for (const line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.substring(6);
            if (dataStr === '[DONE]') {
              input.disabled = false;
              document.getElementById('chatSendFull').disabled = false;
              input.focus();
              
              // On sauvegarde l'historique
              history.push({role: "user", content: text});
              history.push({role: "assistant", content: fullResponse});
              break;
            }
            
            try {
              const data = JSON.parse(dataStr);
              if (data.content) {
                fullResponse += data.content;
                placeholderMsg.innerHTML = formatResponse(fullResponse);
                windowEl.scrollTop = windowEl.scrollHeight;
              } else if (data.sources && data.sources.length > 0) {
                const sourceHtml = `<div style="margin-top:8px; padding-top:8px; border-top:1px dashed rgba(255,255,255,0.1); font-size:10px; color:rgba(255,255,255,0.4);">Sources : ${data.sources.join(' | ')}</div>`;
                placeholderMsg.innerHTML = formatResponse(fullResponse) + sourceHtml;
                windowEl.scrollTop = windowEl.scrollHeight;
              } else if (data.error) {
                placeholderMsg.innerHTML = `<span style="color:#ED2939;">Erreur API: ${data.error}</span>`;
                input.disabled = false;
                document.getElementById('chatSendFull').disabled = false;
              }
            } catch(e) {
              // Ignore parse errors on incomplete chunks
            }
          }
        }
      }
    }).catch(error => {
      placeholderMsg.innerHTML = `<span style="color:#ED2939;">Serveur injoignable. Le backend est-il lancé ?</span>`;
      input.disabled = false;
      document.getElementById('chatSendFull').disabled = false;
    });
  }

  function formatResponse(text) {
    return escapeHTML(text).replace(/\n/g, '<br>');
  }

  function appendMessage(role, content, isPlaceholder = false) {
    const div = document.createElement('div');
    div.className = `chat-message ${role}-msg`;
    div.style.marginBottom = '12px';
    div.style.fontSize = '12px';
    div.style.lineHeight = '1.4';
    
    if (role === 'user') {
      div.style.color = '#f5f5f5';
      div.style.textAlign = 'right';
      div.innerHTML = `<span style="background:rgba(255,255,255,0.08); padding:8px 12px; border-radius:12px 12px 0 12px; display:inline-block;">${escapeHTML(content)}</span>`;
    } else {
      div.style.color = 'var(--text-secondary)';
      div.innerHTML = `<span style="background:rgba(255,255,255,0.03); padding:8px 12px; border-radius:12px 12px 12px 0; display:inline-block; border:1px solid var(--border-light);">${content}</span>`;
    }
    
    windowEl.appendChild(div);
    windowEl.scrollTop = windowEl.scrollHeight;
    
    return div.querySelector('span');
  }

  function afficherMessageBlocage(detail) {
    const messageHTML = `
        <div class="rate-limit-blocage">
            <h3 style="margin-top:0;">Quota quotidien atteint</h3>
            <p>${detail.message}</p>
            <p class="limite-info">Limite quotidienne : ${detail.limite} ${
                detail.action === 'chat' ? 'questions' : 'débats'
            } par adresse IP.</p>
            <div class="rate-limit-soutien">
                <p class="petit" style="font-size:11px; color:rgba(255,255,255,0.4); margin-bottom:8px;">
                    Ce projet citoyen est développé bénévolement et son fonctionnement
                    a un coût en infrastructures et en API d'intelligence artificielle.
                    Si vous souhaitez soutenir son existence, vous pouvez contribuer
                    librement sur <a href="/soutenir/" style="color:var(--rouge-france); text-decoration:underline;">notre page de soutien</a>.
                </p>
                <p class="petit" style="font-size:10px; color:rgba(255,255,255,0.3); font-style:italic;">
                    Aucun don ne donne droit à un accès prioritaire : votre contribution
                    soutient le projet, pas votre propre usage.
                </p>
            </div>
        </div>
    `;
    const div = document.createElement('div');
    div.innerHTML = messageHTML;
    windowEl.appendChild(div);
    windowEl.scrollTop = windowEl.scrollHeight;
  }

  function escapeHTML(str) {
    return str.replace(/[&<>'"]/g, 
      tag => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;'
      }[tag] || tag)
    );
  }
});