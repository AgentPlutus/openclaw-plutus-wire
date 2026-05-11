// X / Twitter GraphQL helpers — shared across Plutus Wire adapters.
// resolveTwitterQueryId + sanitizeQueryId are vendored from upstream
// `clis/twitter/shared.js` (OpenCLI). Live queryIds rotate weekly when X
// rebuilds client-web bundles, so we resolve at runtime against
// fa0311/twitter-openapi placeholder.json with a regex scrape fallback.
// Hard-coded fallback IDs are passed in by callers (timeline.js etc).

const QUERY_ID_PATTERN = /^[A-Za-z0-9_-]+$/;

// from upstream clis/twitter/shared.js — public web client bearer.
// Same value used by every Twitter web client; encoded once, decoded at use.
export const X_BEARER_TOKEN = 'AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA';

// from upstream clis/twitter/shared.js
export function sanitizeQueryId(resolved, fallbackId) {
    return typeof resolved === 'string' && QUERY_ID_PATTERN.test(resolved) ? resolved : fallbackId;
}

// from upstream clis/twitter/shared.js — verbatim except trailing __test__ block.
export async function resolveTwitterQueryId(page, operationName, fallbackId) {
    const resolved = await page.evaluate(`async () => {
    const operationName = ${JSON.stringify(operationName)};
    try {
      const ghResp = await fetch('https://raw.githubusercontent.com/fa0311/twitter-openapi/refs/heads/main/src/config/placeholder.json');
      if (ghResp.ok) {
        const data = await ghResp.json();
        const entry = data?.[operationName];
        if (entry && entry.queryId) return entry.queryId;
      }
    } catch {}
    try {
      const scripts = performance.getEntriesByType('resource')
        .filter(r => r.name.includes('client-web') && r.name.endsWith('.js'))
        .map(r => r.name);
      for (const scriptUrl of scripts.slice(0, 15)) {
        try {
          const text = await (await fetch(scriptUrl)).text();
          const re = new RegExp('queryId:"([A-Za-z0-9_-]+)"[^}]{0,200}operationName:"' + operationName + '"');
          const match = text.match(re);
          if (match) return match[1];
        } catch {}
      }
    } catch {}
    return null;
  }`);
    return sanitizeQueryId(resolved, fallbackId);
}

// Cookie extraction promoted to shared util so health.js can reuse.
// Same expression as inline in upstream timeline.js func body.
export async function getCt0(page) {
    return await page.evaluate(`() => {
        return document.cookie.split(';').map(c=>c.trim()).find(c=>c.startsWith('ct0='))?.split('=')[1] || null;
    }`);
}

// HomeTimeline FEATURES lifted out so adapters rebuild GraphQL URLs from one
// source of truth.
// X's GraphQL rejects requests missing any feature flag.
export function getXFeatures() {
    return {
        rweb_video_screen_enabled: false,
        profile_label_improvements_pcf_label_in_post_enabled: true,
        rweb_tipjar_consumption_enabled: true,
        verified_phone_label_enabled: false,
        creator_subscriptions_tweet_preview_api_enabled: true,
        responsive_web_graphql_timeline_navigation_enabled: true,
        responsive_web_graphql_skip_user_profile_image_extensions_enabled: false,
        premium_content_api_read_enabled: false,
        communities_web_enable_tweet_community_results_fetch: true,
        c9s_tweet_anatomy_moderator_badge_enabled: true,
        responsive_web_grok_analyze_button_fetch_trends_enabled: false,
        responsive_web_grok_analyze_post_followups_enabled: true,
        responsive_web_jetfuel_frame: false,
        responsive_web_grok_share_attachment_enabled: true,
        articles_preview_enabled: true,
        responsive_web_edit_tweet_api_enabled: true,
        graphql_is_translatable_rweb_tweet_is_translatable_enabled: true,
        view_counts_everywhere_api_enabled: true,
        longform_notetweets_consumption_enabled: true,
        responsive_web_twitter_article_tweet_consumption_enabled: true,
        tweet_awards_web_tipping_enabled: false,
        responsive_web_grok_show_grok_translated_post: false,
        responsive_web_grok_analysis_button_from_backend: false,
        creator_subscriptions_quote_tweet_preview_enabled: false,
        freedom_of_speech_not_reach_fetch_enabled: true,
        standardized_nudges_misinfo: true,
        tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled: true,
        longform_notetweets_rich_text_read_enabled: true,
        longform_notetweets_inline_media_enabled: true,
        responsive_web_grok_image_annotation_enabled: true,
        responsive_web_enhance_cards_enabled: false,
    };
}

// Standard auth header set for any X GraphQL fetch under user session.
// Caller provides ct0; we wrap so each cli doesn't reassemble by hand.
export function buildXHeaders(ct0) {
    return {
        Authorization: `Bearer ${decodeURIComponent(X_BEARER_TOKEN)}`,
        'X-Csrf-Token': ct0,
        'X-Twitter-Auth-Type': 'OAuth2Session',
        'X-Twitter-Active-User': 'yes',
    };
}
