/* Replaces the bits of Squarespace's JavaScript this static site needs. */
(function () {
  var body = document.body;
  // Header height variable (Squarespace sets this for the transparent header)
  var header = document.getElementById('header');
  function setH() { if (header) document.documentElement.style.setProperty('--header-height', header.getBoundingClientRect().height + 'px'); }
  setH(); window.addEventListener('resize', setH); window.addEventListener('load', setH);

  // Mobile menu
  var burgers = document.querySelectorAll('.header-burger-btn');
  function closeFolders() {
    document.querySelectorAll('.header-menu-nav-folder--active').forEach(function (f) { f.classList.remove('header-menu-nav-folder--active'); });
    document.querySelectorAll('.header-menu-nav-folder--open').forEach(function (f) { f.classList.remove('header-menu-nav-folder--open'); });
  }
  burgers.forEach(function (b) {
    b.addEventListener('click', function () {
      var open = !body.classList.contains('header--menu-open');
      body.classList.toggle('header--menu-open', open);
      burgers.forEach(function (x) { x.classList.toggle('burger--active', open); x.setAttribute('aria-expanded', open); });
      document.querySelectorAll('.header-menu').forEach(function (m) { m.classList.toggle('header-menu--active', open); });
      if (!open) closeFolders();
      setH();
    });
  });
  // Mobile menu folders
  document.querySelectorAll('.header-menu a[data-folder-id]').forEach(function (a) {
    a.addEventListener('click', function (e) {
      e.preventDefault();
      var id = a.getAttribute('data-folder-id');
      var f = document.querySelector('.header-menu-nav-folder[data-folder="' + id + '"]');
      var root = document.querySelector('.header-menu-nav-folder[data-folder="root"]');
      if (f) f.classList.add('header-menu-nav-folder--active');
      if (root) root.classList.add('header-menu-nav-folder--open');
    });
  });
  document.querySelectorAll('.header-menu a[data-action="back"]').forEach(function (a) {
    a.addEventListener('click', function (e) { e.preventDefault(); closeFolders(); });
  });
  // Desktop folders: open on click/tap as well as hover
  document.querySelectorAll('.header-nav-folder-title').forEach(function (b) {
    b.addEventListener('click', function (e) {
      e.preventDefault();
      var item = b.closest('.header-nav-item--folder');
      var open = !item.classList.contains('header-nav-item--folder--open');
      document.querySelectorAll('.header-nav-item--folder--open').forEach(function (x) { x.classList.remove('header-nav-item--folder--open'); });
      item.classList.toggle('header-nav-item--folder--open', open);
      b.setAttribute('aria-expanded', open);
    });
  });
  document.addEventListener('click', function (e) {
    if (!e.target.closest('.header-nav-item--folder'))
      document.querySelectorAll('.header-nav-item--folder--open').forEach(function (x) { x.classList.remove('header-nav-item--folder--open'); });
  });
  // Fixed header: Squarespace adds "shrink" state when scrolled
  function onScroll() { body.classList.toggle('header--scrolled', window.scrollY > 0); if (header) header.classList.toggle('shrink', window.scrollY > 0); }
  window.addEventListener('scroll', onScroll, { passive: true }); onScroll();

  // Events: move items whose end has passed into the "past" list
  var up = document.querySelector('.eventlist--upcoming'), past = document.querySelector('.eventlist--past');
  if (up && past) {
    var now = Date.now();
    Array.prototype.slice.call(up.querySelectorAll('.eventlist-event[data-end]')).reverse().forEach(function (ev) {
      if (Date.parse(ev.getAttribute('data-end')) < now) {
        ev.classList.remove('eventlist-event--upcoming'); ev.classList.add('eventlist-event--past');
        past.insertBefore(ev, past.firstChild);
      }
    });
  }

  // Forms -> /api/form
  document.querySelectorAll('form.fbc-form').forEach(function (form) {
    form.addEventListener('submit', function (e) {
      e.preventDefault();
      var btn = form.querySelector('button[type=submit]');
      var ok = form.querySelector('.form-submission-text'), err = form.querySelector('.form-error-text');
      err.hidden = true; btn.disabled = true;
      var data = new FormData(form); data.append('_page', location.pathname);
      fetch('/api/form', { method: 'POST', body: data, headers: { 'Accept': 'application/json' } })
        .then(function (r) { return r.json().then(function (j) { if (!r.ok || !j.ok) throw new Error(j.error || 'failed'); }); })
        .then(function () {
          Array.prototype.forEach.call(form.children, function (c) { if (c !== ok) c.hidden = true; });
          ok.hidden = false;
        })
        .catch(function () { err.hidden = false; btn.disabled = false; });
    });
  });
})();
document.addEventListener('click',function(e){var c=e.target.closest('.sqs-announcement-bar-close');if(c){var d=c.closest('.sqs-announcement-bar-dropzone');if(d)d.style.display='none';try{sessionStorage.fbcAnnClosed=1}catch(_){}}});
try{if(sessionStorage.fbcAnnClosed){var _d=document.querySelector('.sqs-announcement-bar-dropzone');if(_d)_d.style.display='none'}}catch(_){}
(function(){var now=Date.now();document.querySelectorAll('.summary-item-list').forEach(function(l){var n=0;l.querySelectorAll('.summary-item').forEach(function(it){var e=it.getAttribute('data-end');if(e&&Date.parse(e)<now){it.style.display='none';return}if(++n>6)it.style.display='none'})})})();
document.querySelectorAll('.sqs-video-wrapper[data-html]').forEach(function(w){if(!w.querySelector('iframe')){w.innerHTML=w.getAttribute('data-html');var f=w.querySelector('iframe');if(f){f.style.cssText='position:absolute;top:0;left:0;width:100%;height:100%';f.removeAttribute('width');f.removeAttribute('height')}}});
