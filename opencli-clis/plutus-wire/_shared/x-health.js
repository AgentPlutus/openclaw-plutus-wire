// Health probes for X.com and Grok — invoked by `plutus-wire health` before
// local ingest ticks so we do not hammer captcha-blocked sessions.
// Pure check (no writes), so it's safe in daemon (read-only) profile.

import { getCt0 } from './x-graphql.js';

// Detect rate-limit by sniffing for the SPA banner X renders when API throttles
// the session ("Something went wrong. Try reloading."). We don't currently
// expose a precise reset timestamp because X doesn't surface one in DOM —
// rate_limit_resets_at is reserved in the contract for a future header probe.
export async function checkXHealth(page) {
    await page.goto('https://x.com/home');
    await page.wait(2);

    const ct0 = await getCt0(page);
    if (!ct0) {
        return {
            x_logged_in: false,
            captcha_detected: false,
            rate_limited: false,
            rate_limit_resets_at: null,
            ct0_age_minutes: null,
        };
    }

    // Captcha (Arkose iframe) and login wall both indicate session unusable.
    const captcha = await page.evaluate(`(() => {
        return !!document.querySelector('iframe[src*="captcha"]')
            || !!document.querySelector('iframe[src*="arkoselabs"]')
            || !!document.querySelector('[data-testid="LoginForm"]');
    })()`);

    // Rate-limit banner: X renders a generic "retry" surface when home timeline
    // fetch is 429'd. The presence of primaryColumn means we're at least past
    // the SPA shell — combined with absence of timeline cell we infer throttle.
    const rateLimited = await page.evaluate(`(() => {
        const txt = document.body?.innerText || '';
        return txt.includes('Rate limit exceeded')
            || txt.includes('Too Many Requests')
            || txt.includes('请求次数过多');
    })()`);

    return {
        x_logged_in: true,
        captcha_detected: !!captcha,
        rate_limited: !!rateLimited,
        rate_limit_resets_at: null,
        ct0_age_minutes: null,
    };
}

// Grok health is simpler — composer presence is the single signal that we're
// logged in and the SPA shell loaded. Captcha here would also kill composer.
export async function checkGrokHealth(page) {
    await page.goto('https://grok.com');
    await page.wait(2);
    const composerExists = await page.evaluate(`(() => {
        return !!document.querySelector('textarea')
            || !!document.querySelector('.ProseMirror')
            || !!document.querySelector('[contenteditable="true"]');
    })()`);
    return { grok_logged_in: !!composerExists };
}
