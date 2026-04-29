(function () {
  'use strict';

  // Mobile nav toggle
  const toggle = document.getElementById('nav-toggle');
  const nav = document.getElementById('primary-nav');

  if (toggle && nav) {
    const setOpen = (open) => {
      toggle.setAttribute('aria-expanded', open ? 'true' : 'false');
      nav.classList.toggle('open', open);
      toggle.setAttribute('aria-label', open ? 'Close menu' : 'Open menu');
    };

    toggle.addEventListener('click', () => {
      setOpen(toggle.getAttribute('aria-expanded') !== 'true');
    });

    // Close after tapping a link on mobile
    nav.querySelectorAll('a').forEach((a) => {
      a.addEventListener('click', () => {
        if (window.matchMedia('(max-width: 720px)').matches) setOpen(false);
      });
    });

    // Close on Escape, or when window grows past mobile
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') setOpen(false);
    });
    window.addEventListener('resize', () => {
      if (!window.matchMedia('(max-width: 720px)').matches) setOpen(false);
    });
  }

  // Footer year
  const yearLine = document.getElementById('year-line');
  if (yearLine) {
    yearLine.textContent = '© ' + new Date().getFullYear() + ' FTS Net Mon contributors.';
  }

  // Reveal-on-scroll for cards / steps (progressive enhancement)
  if ('IntersectionObserver' in window) {
    const targets = document.querySelectorAll('.card, .steps li, .arch-box, .preview-window');
    targets.forEach((t) => {
      t.style.opacity = '0';
      t.style.transform = 'translateY(12px)';
      t.style.transition = 'opacity 480ms ease, transform 480ms ease';
    });

    const io = new IntersectionObserver((entries) => {
      entries.forEach((e) => {
        if (e.isIntersecting) {
          e.target.style.opacity = '1';
          e.target.style.transform = 'translateY(0)';
          io.unobserve(e.target);
        }
      });
    }, { threshold: 0.12, rootMargin: '0px 0px -40px 0px' });

    targets.forEach((t) => io.observe(t));
  }
})();
