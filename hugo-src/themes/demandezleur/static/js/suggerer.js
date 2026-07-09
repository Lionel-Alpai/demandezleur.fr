document.addEventListener('DOMContentLoaded', function () {
  const form     = document.getElementById('suggerer-form');
  const submit   = document.getElementById('sg-submit');
  const result   = document.getElementById('sg-result');
  const candidat = document.getElementById('sg-candidat');
  const titre    = document.getElementById('sg-titre');
  const notes    = document.getElementById('sg-notes');
  const notesCount = document.getElementById('sg-notes-chars');
  const fileInput  = document.getElementById('sg-fichier');
  const dropZone   = document.getElementById('file-drop-zone');
  const fileName   = document.getElementById('file-name');
  const browseBtn  = document.getElementById('file-browse-btn');

  // Compteur notes
  notes.addEventListener('input', function () {
    notesCount.textContent = notes.value.length;
  });

  // Validation → activer le bouton
  function validate() {
    submit.disabled = !(candidat.value && titre.value.trim().length >= 3);
  }
  candidat.addEventListener('change', validate);
  titre.addEventListener('input', validate);

  // Gestion du fichier
  browseBtn.addEventListener('click', function () { fileInput.click(); });
  dropZone.addEventListener('click', function (e) {
    if (e.target !== browseBtn) fileInput.click();
  });

  fileInput.addEventListener('change', function () {
    if (fileInput.files.length > 0) {
      afficherFichier(fileInput.files[0]);
    }
  });

  dropZone.addEventListener('dragover', function (e) {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone.addEventListener('dragleave', function () {
    dropZone.classList.remove('drag-over');
  });
  dropZone.addEventListener('drop', function (e) {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const f = e.dataTransfer.files[0];
    if (f) {
      const dt = new DataTransfer();
      dt.items.add(f);
      fileInput.files = dt.files;
      afficherFichier(f);
    }
  });

  function afficherFichier(f) {
    const maxMo = 20 * 1024 * 1024;
    if (f.size > maxMo) {
      showResult('error', 'Fichier trop volumineux (maximum 20 Mo).');
      fileInput.value = '';
      return;
    }
    dropZone.classList.add('has-file');
    fileName.textContent = f.name + ' (' + (f.size / 1024).toFixed(0) + ' Ko)';
    fileName.style.display = 'block';
    document.querySelector('.file-label').style.display = 'none';
    document.querySelector('.file-icon').style.display = 'none';
  }

  // Soumission
  form.addEventListener('submit', async function (e) {
    e.preventDefault();
    submit.disabled = true;
    submit.textContent = 'Envoi en cours…';
    result.style.display = 'none';

    const data = new FormData();
    data.append('candidat', candidat.value);
    data.append('titre', titre.value.trim());
    data.append('url', document.getElementById('sg-url').value.trim());
    data.append('notes', notes.value.trim());
    if (fileInput.files.length > 0) {
      data.append('fichier', fileInput.files[0]);
    }

    try {
      const resp = await fetch('/api/suggerer-document', {
        method: 'POST',
        body: data,
      });
      const json = await resp.json();
      if (json.success) {
        showResult('success', 'Merci ! Votre suggestion a bien été transmise. Elle sera examinée manuellement avant toute intégration.');
        form.reset();
        dropZone.classList.remove('has-file');
        fileName.style.display = 'none';
        document.querySelector('.file-label').style.display = '';
        document.querySelector('.file-icon').style.display = '';
        notesCount.textContent = '0';
      } else {
        showResult('error', json.message_utilisateur || 'Une erreur est survenue.');
      }
    } catch (err) {
      showResult('error', 'Impossible de joindre le serveur. Vérifiez votre connexion.');
    }

    submit.textContent = 'Envoyer la suggestion';
    validate();
  });

  function showResult(type, msg) {
    result.className = 'sg-result ' + type;
    result.textContent = msg;
    result.style.display = 'block';
    result.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }
});
