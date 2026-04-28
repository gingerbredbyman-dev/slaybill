// SLAYBILL — upgrade-nudge.js
// Injects contextual Pro upsell panels into Tier 2 detail pages on Fan tier only.
// Reads /config/tier.json (loaded by data-resolver) and quietly no-ops on Pro.
//
// Used by: web/shows/_template.html
// Pairs with: web/assets/js/data-resolver.js

const NUDGE_CTAS = [
  {
    id: 'editorial',
    headline: 'Pro tracks the story behind this show',
    body: 'Weekly editorial digest with multi-source verification, critic-vs-audience deltas, and producer signal.',
    cta: 'See Pro',
  },
  {
    id: 'grosses',
    headline: 'Pro charts 8 weeks of grosses for this show',
    body: 'Week-over-week capacity, average ticket, and the moment a show pivots.',
    cta: 'See Pro',
  },
  {
    id: 'cast',
    headline: 'Pro tracks rotating leads + standby calls',
    body: 'Know who is on for tonight before you walk to the box office.',
    cta: 'See Pro',
  },
];

const DISMISS_KEY = 'slaybill:nudge:dismissed';
const SESSION_SHOWN_KEY = 'slaybill:nudge:shown-this-session';

function pickNudge(slug) {
  const dismissed = JSON.parse(localStorage.getItem(DISMISS_KEY) || '[]');
  const candidates = NUDGE_CTAS.filter((n) => !dismissed.includes(n.id));
  if (candidates.length === 0) return null;
  // Stable pick per show: hash slug to index.
  let h = 0;
  for (let i = 0; i < slug.length; i++) h = (h * 31 + slug.charCodeAt(i)) >>> 0;
  return candidates[h % candidates.length];
}

function buildNudge(nudge, upgradeUrl) {
  const wrap = document.createElement('aside');
  wrap.className = 'upgrade-nudge';
  wrap.setAttribute('aria-label', 'SLAYBILL Pro upgrade');
  wrap.innerHTML = `
    <button class="upgrade-nudge__dismiss" aria-label="Dismiss">×</button>
    <h3 class="upgrade-nudge__headline">${nudge.headline}</h3>
    <p class="upgrade-nudge__body">${nudge.body}</p>
    <a class="upgrade-nudge__cta" href="${upgradeUrl}" rel="noopener">${nudge.cta} →</a>
  `;
  wrap.querySelector('.upgrade-nudge__dismiss').addEventListener('click', () => {
    const dismissed = JSON.parse(localStorage.getItem(DISMISS_KEY) || '[]');
    if (!dismissed.includes(nudge.id)) dismissed.push(nudge.id);
    localStorage.setItem(DISMISS_KEY, JSON.stringify(dismissed));
    wrap.remove();
  });
  return wrap;
}

function injectStyles() {
  if (document.getElementById('upgrade-nudge-styles')) return;
  const style = document.createElement('style');
  style.id = 'upgrade-nudge-styles';
  style.textContent = `
    .upgrade-nudge {
      position: relative;
      max-width: 1100px;
      margin: 32px auto;
      padding: 20px 24px;
      background: color-mix(in oklch, var(--c1, #888) 12%, transparent);
      border: 1px solid color-mix(in oklch, var(--c1, #888) 35%, transparent);
      border-radius: 14px;
      backdrop-filter: blur(6px);
      -webkit-backdrop-filter: blur(6px);
    }
    .upgrade-nudge__dismiss {
      position: absolute; top: 8px; right: 12px;
      background: none; border: 0;
      color: var(--ink-muted, #888);
      font-size: 20px; line-height: 1; cursor: pointer;
      padding: 4px 8px;
    }
    .upgrade-nudge__dismiss:hover { color: var(--ink, #000); }
    .upgrade-nudge__headline {
      margin: 0 0 8px;
      font-family: Fraunces, Georgia, serif;
      font-size: 18px; font-weight: 500;
      color: var(--ink, #000);
    }
    .upgrade-nudge__body {
      margin: 0 0 12px;
      color: var(--ink-muted, #555);
      font-size: 14px; line-height: 1.5;
    }
    .upgrade-nudge__cta {
      display: inline-block;
      padding: 8px 14px;
      background: var(--c1, #000);
      color: var(--stage, #fff);
      text-decoration: none;
      border-radius: 999px;
      font-size: 13px; font-weight: 500;
      letter-spacing: 0.04em;
      transition: transform .2s ease;
    }
    .upgrade-nudge__cta:hover { transform: translateY(-1px); }
    @media (prefers-reduced-motion: reduce) {
      .upgrade-nudge__cta { transition: none; }
    }
  `;
  document.head.appendChild(style);
}

export async function setupUpgradeNudge(slug, mountSelector = 'main') {
  let cfg;
  try {
    cfg = await fetch('../config/tier.json').then((r) => r.json());
  } catch {
    return; // No config = no nudge.
  }
  if (cfg.tier !== 'fan' || cfg.show_upgrade_nudges === false) return;
  if (sessionStorage.getItem(SESSION_SHOWN_KEY) === slug) return;
  const nudge = pickNudge(slug);
  if (!nudge) return;
  injectStyles();
  const mount = document.querySelector(mountSelector);
  if (!mount) return;
  mount.appendChild(buildNudge(nudge, cfg.pro_upgrade_url || 'https://slaybill.app/pro'));
  sessionStorage.setItem(SESSION_SHOWN_KEY, slug);
}
