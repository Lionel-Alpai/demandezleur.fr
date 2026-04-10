document.addEventListener('DOMContentLoaded', function() {
  const track = document.getElementById('track');
  const dots = document.querySelectorAll('#dots .cdot');
  
  if (!track) return; // Pas sur la homepage

  let current = 0;
  const slides = Array.from(track.children);
  const total = slides.length;
  let autoTimer;

  // Randomiser l'ordre des slides au chargement
  function shuffleSlides() {
    for (let i = slides.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      track.appendChild(slides[j]);
    }
    // Re-sélectionner les slides après shuffle
    return Array.from(track.children);
  }
  
  // Appliquer le shuffle
  const shuffledSlides = shuffleSlides();

  function goTo(i) {
    current = i;
    track.style.transform = 'translateX(-' + (i * 100) + '%)';
    dots.forEach(function(d, idx) { d.classList.toggle('active', idx === i); });
  }

  function startAuto() { 
    if (total > 1) {
      autoTimer = setInterval(function() { goTo((current + 1) % total); }, 3500); 
    }
  }

  function resetAuto() { 
    clearInterval(autoTimer); 
    startAuto(); 
  }

  dots.forEach(function(d) {
    d.addEventListener('click', function() { 
      goTo(parseInt(d.dataset.i)); 
      resetAuto(); 
    });
  });

  startAuto();

  let startX = 0;
  const cw = document.querySelector('.carousel-window');
  if (cw) {
    cw.addEventListener('touchstart', function(e) { startX = e.touches[0].clientX; }, {passive: true});
    cw.addEventListener('touchend', function(e) {
      const diff = startX - e.changedTouches[0].clientX;
      if (Math.abs(diff) > 40) {
        if (diff > 0 && current < total - 1) goTo(current + 1);
        else if (diff < 0 && current > 0) goTo(current - 1);
        resetAuto();
      }
    }, {passive: true});
  }

});