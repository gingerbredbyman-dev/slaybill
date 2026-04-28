/**
 * SLAYBILL data resolver — tier-aware data fetcher.
 *
 * Resolves show data by trying, in order:
 *   1. Pro cache (https://slaybill-pro-cache.<domain>/shows_live.json)
 *      Used by Fan tier when pro_cache_url is set in config/tier.json
 *      and the cache is fresh (within pro_cache_max_age_days).
 *   2. Local data/shows_live.json
 *      Always tried as a fallback. Pro tier reads this directly (it generates it).
 *   3. localStorage cache
 *      Last-known-good data, persisted from any successful prior load.
 *
 * Returns { data, source, age_days } where source is one of:
 *   'pro_cache' | 'local' | 'cached' | 'error'
 *
 * Usage:
 *   import { resolveShowData, formatTierBadge } from './data-resolver.js';
 *   const { data, source, age_days } = await resolveShowData();
 *   document.getElementById('tier-badge').textContent =
 *     formatTierBadge(source, age_days);
 */

const CACHE_KEY = 'slaybill.shows_live.cached.v1';
const CACHE_TIMESTAMP_KEY = 'slaybill.shows_live.cached_at.v1';

async function loadConfig() {
  try {
    const r = await fetch('config/tier.json', { cache: 'no-store' });
    if (!r.ok) throw new Error(`config/tier.json: ${r.status}`);
    return await r.json();
  } catch (e) {
    console.warn('[data-resolver] config/tier.json missing, defaulting to fan tier', e);
    return {
      tier: 'fan',
      tier_label: 'SLAYBILL',
      pro_cache_url: null,
      pro_cache_max_age_days: 7,
      show_upgrade_nudges: true,
    };
  }
}

function ageInDays(iso) {
  if (!iso) return Infinity;
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return Infinity;
  return (Date.now() - t) / 86_400_000;
}

async function tryProCache(url) {
  if (!url) return null;
  try {
    const r = await fetch(url, { cache: 'no-store' });
    if (!r.ok) return null;
    return await r.json();
  } catch (e) {
    console.info('[data-resolver] Pro cache unreachable:', e.message);
    return null;
  }
}

async function tryLocal() {
  try {
    const r = await fetch('data/shows_live.json', { cache: 'no-store' });
    if (!r.ok) return null;
    return await r.json();
  } catch (e) {
    console.info('[data-resolver] Local shows_live.json unreachable:', e.message);
    return null;
  }
}

function tryCached() {
  try {
    const raw = localStorage.getItem(CACHE_KEY);
    if (!raw) return null;
    return JSON.parse(raw);
  } catch (e) {
    return null;
  }
}

function persistCache(data) {
  try {
    localStorage.setItem(CACHE_KEY, JSON.stringify(data));
    localStorage.setItem(CACHE_TIMESTAMP_KEY, new Date().toISOString());
  } catch (e) {
    /* quota — non-fatal */
  }
}

export async function resolveShowData() {
  const config = await loadConfig();
  const isFan = config.tier === 'fan';
  const proUrl = config.pro_cache_url;
  const maxAge = config.pro_cache_max_age_days || 7;

  // 1. Fan tier with a configured Pro cache: try cache first.
  if (isFan && proUrl) {
    const cacheData = await tryProCache(proUrl);
    if (cacheData) {
      const age = ageInDays(cacheData.generated_at);
      if (age <= maxAge) {
        persistCache(cacheData);
        return { data: cacheData, source: 'pro_cache', age_days: age, config };
      }
      console.info(`[data-resolver] Pro cache stale (${age.toFixed(1)}d > ${maxAge}d) — falling through`);
    }
  }

  // 2. Local shows_live.json (Pro tier always uses this; Fan tier falls here when cache misses).
  const localData = await tryLocal();
  if (localData) {
    persistCache(localData);
    const age = ageInDays(localData.generated_at);
    return {
      data: localData,
      source: isFan ? 'fan_scrape' : 'local',
      age_days: age,
      config,
    };
  }

  // 3. localStorage cached fallback (offline, server down, etc.).
  const cached = tryCached();
  if (cached) {
    const age = ageInDays(cached.generated_at);
    return { data: cached, source: 'cached', age_days: age, config };
  }

  return { data: null, source: 'error', age_days: Infinity, config };
}

/** Format a human-readable badge string for the source + age. */
export function formatTierBadge(source, ageDays) {
  if (source === 'pro_cache') {
    const age = formatAge(ageDays);
    return `Austin Verified · ${age}`;
  }
  if (source === 'fan_scrape') {
    const age = formatAge(ageDays);
    return `Updated ${age}`;
  }
  if (source === 'local') {
    const age = formatAge(ageDays);
    return `Pro · ${age}`;
  }
  if (source === 'cached') {
    return 'Cached · offline';
  }
  return 'Data unavailable';
}

function formatAge(days) {
  if (!Number.isFinite(days)) return 'unknown';
  if (days < 1) {
    const h = Math.max(1, Math.round(days * 24));
    return `${h}h ago`;
  }
  if (days < 14) return `${Math.round(days)}d ago`;
  return `${Math.round(days / 7)}w ago`;
}
