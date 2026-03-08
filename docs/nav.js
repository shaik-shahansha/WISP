/* WISP Docs — shared navigation & interactivity */

(function () {
  'use strict';

  /* ---------- Hamburger / sidebar ---------- */
  function initSidebar() {
    const btn  = document.getElementById('hamburger');
    const side = document.getElementById('sidebar');
    const overlay = document.getElementById('overlay');
    if (!btn || !side) return;
    btn.addEventListener('click', () => {
      const open = side.classList.toggle('open');
      if (overlay) overlay.style.display = open ? 'block' : 'none';
    });
    if (overlay) overlay.addEventListener('click', () => {
      side.classList.remove('open');
      overlay.style.display = 'none';
    });
  }

  /* ---------- Active sidebar link ---------- */
  function markActiveLink() {
    const path = location.pathname.split('/').pop() || 'index.html';
    document.querySelectorAll('.sidebar-link, .topbar-nav a').forEach(a => {
      const href = a.getAttribute('href') || '';
      const target = href.split('/').pop();
      if (target === path || (path === '' && target === 'index.html')) {
        a.classList.add('active');
      }
    });
  }

  /* ---------- Copy code buttons ---------- */
  function initCopyButtons() {
    document.querySelectorAll('.code-block').forEach(block => {
      const btn = block.querySelector('.code-copy');
      if (!btn) return;
      btn.addEventListener('click', () => {
        const code = block.querySelector('pre').innerText;
        navigator.clipboard.writeText(code).then(() => {
          btn.textContent = 'Copied!';
          setTimeout(() => { btn.textContent = 'Copy'; }, 1800);
        });
      });
    });
  }

  /* ---------- Hero tab switcher ---------- */
  function initHeroTabs() {
    document.querySelectorAll('.hct').forEach(tab => {
      tab.addEventListener('click', () => {
        const group = tab.closest('.hero-code');
        group.querySelectorAll('.hct').forEach(t => t.classList.remove('active'));
        group.querySelectorAll('.hero-pane').forEach(p => p.classList.remove('active'));
        tab.classList.add('active');
        const target = group.querySelector(tab.dataset.target);
        if (target) target.classList.add('active');
      });
    });
  }

  /* ---------- TOC scroll spy ---------- */
  function initScrollSpy() {
    const toc = document.querySelector('.toc');
    if (!toc) return;
    const headings = Array.from(document.querySelectorAll('h2[id], h3[id]'));
    if (!headings.length) return;

    const tocLinks = {};
    toc.querySelectorAll('a[href]').forEach(a => {
      const id = a.getAttribute('href').replace('#', '');
      tocLinks[id] = a;
    });

    const observer = new IntersectionObserver(entries => {
      entries.forEach(e => {
        if (e.isIntersecting) {
          Object.values(tocLinks).forEach(a => a.classList.remove('active'));
          const link = tocLinks[e.target.id];
          if (link) link.classList.add('active');
        }
      });
    }, { rootMargin: '-60px 0px -70% 0px', threshold: 0 });

    headings.forEach(h => observer.observe(h));
  }

  /* ---------- Boot ---------- */
  document.addEventListener('DOMContentLoaded', () => {
    initSidebar();
    markActiveLink();
    initCopyButtons();
    initHeroTabs();
    initScrollSpy();
  });
})();
