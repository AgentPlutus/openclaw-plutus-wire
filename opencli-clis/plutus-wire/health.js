// Plutus Wire health — combined X + Grok session probe. This is a pure
// read-only check used before local ingest ticks.

import { cli, Strategy } from '@jackwener/opencli/registry';
import { checkXHealth, checkGrokHealth } from './_shared/x-health.js';

cli({
    site: 'plutus-wire',
    name: 'health',
    description: 'Combined X + Grok session health probe',
    domain: 'x.com',
    strategy: Strategy.COOKIE,
    browser: true,
    args: [],
    columns: [
        'captured_at',
        'x_logged_in', 'x_captcha_detected', 'x_rate_limited',
        'grok_logged_in',
        'ct0_cookie_age_minutes', 'last_successful_fetch',
    ],
    func: async (page) => {
        const x = await checkXHealth(page).catch((e) => ({
            x_logged_in: false,
            x_captcha_detected: false,
            x_rate_limited: false,
            error: String(e?.message || e),
        }));
        const g = await checkGrokHealth(page).catch((e) => ({
            grok_logged_in: false,
            error: String(e?.message || e),
        }));

        const captured = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
        return [{
            captured_at: captured,
            x_logged_in: !!x.x_logged_in,
            x_captcha_detected: !!(x.x_captcha_detected ?? x.captcha_detected),
            x_rate_limited: !!(x.x_rate_limited ?? x.rate_limited),
            grok_logged_in: !!g.grok_logged_in,
            ct0_cookie_age_minutes: x.ct0_cookie_age_minutes ?? x.ct0_age_minutes ?? null,
            last_successful_fetch: x.last_successful_fetch ?? null,
            x_error: x.error || null,
            grok_error: g.error || null,
        }];
    },
});
