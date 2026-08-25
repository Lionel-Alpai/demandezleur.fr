/* export-image.js — un débat → image 1080×1350 (canvas), téléchargée en PNG. Dépend de dl.js. */
(function () {
  'use strict';
  function lignes(ctx, texte, maxW) {
    var mots = String(texte || '').split(/\s+/), out = [], cur = '';
    mots.forEach(function (m) { var t = cur ? cur + ' ' + m : m; if (ctx.measureText(t).width > maxW && cur) { out.push(cur); cur = m; } else cur = t; });
    if (cur) out.push(cur); return out;
  }
  function meilleure(interventions) {
    var courtes = interventions.filter(function (t) { return t.length <= 700; });
    var src = courtes.length ? courtes : interventions;
    var t = src[src.length - 1] || ''; return t.length > 700 ? t.slice(0, 697).replace(/\s\S*$/, '') + '…' : t;
  }
  function charger(src) { return new Promise(function (res) { var im = new Image(); im.onload = function () { res(im); }; im.onerror = function () { res(null); }; im.src = src; }); }
  DL.exporterImage = function (doc, candidats) {
    var W = 1080, H = 1350, P = 64, cv = document.createElement('canvas'); cv.width = W; cv.height = H;
    var ctx = cv.getContext('2d');
    ctx.fillStyle = '#0a1428'; ctx.fillRect(0, 0, W, H);
    ctx.fillStyle = '#e53946'; ctx.fillRect(0, 0, W, 10);
    ctx.fillStyle = '#ff5f6b'; ctx.font = '600 24px Inter, system-ui, sans-serif'; ctx.fillText('DÉBAT' + (doc.mode === 'arene' ? ' · ARÈNE' : '') + ' · PRÉSIDENTIELLE 2027', P, P + 20);
    ctx.fillStyle = '#f4f6fb'; ctx.font = '800 52px Inter, system-ui, sans-serif';
    var y = P + 80; lignes(ctx, doc.sujet, W - 2 * P).slice(0, 2).forEach(function (l) { ctx.fillText(l, P, y); y += 60; });
    y += 20;
    var ids = doc.candidats.slice(0, 5), hauteur = Math.floor((H - y - 110) / ids.length);
    return Promise.all(ids.map(function (id) { var c = candidats[id]; return c && c.photo ? charger(c.photo) : Promise.resolve(null); })).then(function (imgs) {
      ids.forEach(function (id, k) {
        var c = candidats[id] || { nom: id, parti_court: '' }, textes = [];
        doc.tours.forEach(function (t) { t.interventions.forEach(function (i) { if (i.candidat_id === id) textes.push(i.texte); }); });
        var top = y + k * hauteur;
        ctx.fillStyle = '#111d3a'; ctx.beginPath(); ctx.roundRect(P, top, W - 2 * P, hauteur - 16, 18); ctx.fill();
        if (imgs[k]) { ctx.save(); ctx.beginPath(); ctx.roundRect(P + 20, top + 20, 84, 84, 12); ctx.clip(); ctx.drawImage(imgs[k], P + 20, top + 20, 84, 84); ctx.restore(); }
        ctx.fillStyle = '#f4f6fb'; ctx.font = '700 28px Inter, system-ui, sans-serif'; ctx.fillText(c.nom, P + 124, top + 52);
        ctx.fillStyle = 'rgba(244,246,251,0.6)'; ctx.font = '400 22px Inter, system-ui, sans-serif'; ctx.fillText(c.parti_court || '', P + 124, top + 84);
        ctx.fillStyle = 'rgba(244,246,251,0.88)'; ctx.font = '400 23px Inter, system-ui, sans-serif';
        var ty = top + 128, maxL = Math.floor((hauteur - 150) / 30);
        lignes(ctx, meilleure(textes), W - 2 * P - 40).slice(0, maxL).forEach(function (l) { ctx.fillText(l, P + 20, ty); ty += 30; });
      });
      ctx.fillStyle = 'rgba(244,246,251,0.55)'; ctx.font = '400 22px Inter, system-ui, sans-serif';
      ctx.fillText('demandezleur.fr — réponses générées par IA à partir des programmes officiels', P, H - 60);
      ctx.fillStyle = '#ff5f6b'; ctx.font = '600 22px Inter, system-ui, sans-serif'; ctx.fillText(doc.id ? 'demandezleur.fr/d/?id=' + doc.id : 'demandezleur.fr/debat/', P, H - 28);
      cv.toBlob(function (blob) { var a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'debat-demandezleur' + (doc.id ? '-' + doc.id : '') + '.png'; document.body.appendChild(a); a.click(); a.remove(); }, 'image/png');
    });
  };
})();
