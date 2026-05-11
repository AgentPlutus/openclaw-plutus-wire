// Plutus Wire home-tabs — detects X home timeline tabs visible to the user's
// logged-in browser session. This does not fetch timeline content.

import { AuthRequiredError } from '@jackwener/opencli/errors';
import { cli, Strategy } from '@jackwener/opencli/registry';
import { getCt0 } from './_shared/x-graphql.js';

function slugifyTab(label, href) {
    const text = String(label || '').trim().toLowerCase();
    if (text === 'for you' || text === 'foryou' || text === '为你推荐') return 'for-you';
    if (text === 'following' || text === '正在关注') return 'following';
    if (text === 'ai') return 'ai';
    if (text === 'lists' || text === '列表') return 'lists';
    if (text === 'communities' || text === '社区') return 'communities';
    const fromHref = String(href || '').split('?')[0].split('/').filter(Boolean).pop() || '';
    const base = text || fromHref;
    return base
        .normalize('NFKD')
        .replace(/[^a-z0-9]+/g, '-')
        .replace(/^-+|-+$/g, '') || 'unknown';
}

function supportStatus(slug) {
    if (slug === 'following' || slug === 'for-you' || slug === 'ai') return 'supported';
    if (slug === 'lists' || slug === 'communities') return 'detected_only';
    return 'detected_only';
}

cli({
    site: 'plutus-wire',
    name: 'home-tabs',
    description: 'Detect visible X home timeline tabs for source selection',
    domain: 'x.com',
    strategy: Strategy.COOKIE,
    browser: true,
    args: [],
    columns: ['captured_at', 'x_logged_in', 'tab_count', 'tabs'],
    func: async (page) => {
        const t0 = Date.now();
        await page.goto('https://x.com/home');
        await page.wait(3);
        const ct0 = await getCt0(page);
        if (!ct0) throw new AuthRequiredError('x.com', 'no ct0 cookie');

        const tabs = await page.evaluate(`(() => {
            const candidates = [];
            const seen = new Set();
            const add = (node) => {
                if (!node) return;
                const label = (node.innerText || node.getAttribute('aria-label') || '').trim();
                const href = node.href || node.closest('a')?.href || '';
                if (!label) return;
                const key = label + '|' + href;
                if (seen.has(key)) return;
                seen.add(key);
                const selected = node.getAttribute('aria-selected') === 'true'
                    || node.closest('[aria-selected="true"]') != null;
                candidates.push({ label, href, selected });
            };
            document.querySelectorAll('main [role="tab"], [data-testid="ScrollSnap-List"] [role="tab"]').forEach(add);
            return candidates;
        })()`);

        const normalized = [];
        const seenSlugs = new Set();
        for (const tab of tabs || []) {
            const slug = slugifyTab(tab.label, tab.href);
            if (seenSlugs.has(slug)) continue;
            seenSlugs.add(slug);
            normalized.push({
                slug,
                label: tab.label,
                href: tab.href || null,
                selected: !!tab.selected,
                support: supportStatus(slug),
                default_enabled: slug === 'following' || slug === 'for-you',
            });
        }

        const ranAt = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
        return [{
            captured_at: ranAt,
            x_logged_in: true,
            tab_count: normalized.length,
            latency_ms: Date.now() - t0,
            tabs: normalized,
        }];
    },
});
