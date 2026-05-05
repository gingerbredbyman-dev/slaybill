const MOTION_QUERY = '(prefers-reduced-motion: reduce)';
const REVEAL_SELECTOR = [
  '.cover',
  '.bucket',
  '.ob-row',
  '.more',
  '.page-foot',
  '.show-card',
  '.panel',
  '.poster',
  '.money .cell',
  '.score-card',
  '.tickets',
  '.sources',
].join(',');

function clamp(min, value, max) {
  return Math.min(Math.max(value, min), max);
}

function canMove() {
  return !window.matchMedia(MOTION_QUERY).matches;
}

function observeReveals(root = document) {
  const targets = [...root.querySelectorAll(REVEAL_SELECTOR)]
    .filter((el) => !el.dataset.motionBound);

  if (!targets.length) return;

  for (const el of targets) {
    el.dataset.motionBound = 'true';
    el.classList.add('motion-reveal');
  }

  if (!canMove() || !('IntersectionObserver' in window)) {
    targets.forEach((el) => el.classList.add('is-visible'));
    return;
  }

  const io = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (!entry.isIntersecting) continue;
      entry.target.classList.add('is-visible');
      io.unobserve(entry.target);
    }
  }, { rootMargin: '0px 0px 0px 0px', threshold: 0.02 });

  targets.forEach((el) => io.observe(el));
}

function setupScrollState() {
  if (!canMove()) return;

  let lastY = window.scrollY;
  let lastTime = performance.now();
  let raf = 0;

  const update = () => {
    raf = 0;
    const y = window.scrollY;
    const max = Math.max(1, document.documentElement.scrollHeight - window.innerHeight);
    const now = performance.now();
    const velocity = clamp(-1, (y - lastY) / Math.max(16, now - lastTime), 1);

    document.documentElement.style.setProperty('--scroll-progress', (y / max).toFixed(4));
    document.documentElement.style.setProperty('--scroll-velocity', velocity.toFixed(4));
    document.documentElement.style.setProperty('--scroll-lift', `${(y / max * -120).toFixed(1)}px`);
    document.documentElement.style.setProperty('--cover-lift', `${(y / max * -18).toFixed(1)}px`);
    document.documentElement.style.setProperty('--rail-lift', `${(y / max * 80).toFixed(1)}px`);
    document.documentElement.style.setProperty('--aurora-rotation', `${(y / max * 360).toFixed(1)}deg`);

    lastY = y;
    lastTime = now;
  };

  window.addEventListener('scroll', () => {
    if (!raf) raf = requestAnimationFrame(update);
  }, { passive: true });

  update();
}

function setupPointerLight() {
  if (!canMove()) return;

  let raf = 0;
  let nextX = 0.5;
  let nextY = 0.35;

  window.addEventListener('pointermove', (event) => {
    nextX = event.clientX / Math.max(1, window.innerWidth);
    nextY = event.clientY / Math.max(1, window.innerHeight);
    if (raf) return;
    raf = requestAnimationFrame(() => {
      raf = 0;
      document.documentElement.style.setProperty('--pointer-x', nextX.toFixed(4));
      document.documentElement.style.setProperty('--pointer-y', nextY.toFixed(4));
      document.documentElement.style.setProperty('--pointer-x-pct', `${(nextX * 100).toFixed(1)}%`);
      document.documentElement.style.setProperty('--pointer-y-pct', `${(nextY * 100).toFixed(1)}%`);
      document.documentElement.style.setProperty('--pointer-shift', `${((nextX - 0.5) * 28).toFixed(1)}px`);
    });
  }, { passive: true });
}

export function setupSlaybillMotion() {
  observeReveals();
  setupScrollState();
  setupPointerLight();

  return {
    refresh(root = document) {
      observeReveals(root);
    },
  };
}
