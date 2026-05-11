// Plutus Wire bookmarks — COOKIE strategy. Fetches the authenticated user's X
// bookmarks via the read-only Bookmarks GraphQL endpoint.
//
// Output shape mirrors timeline.js / likes.js.

import { AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors';
import { cli, Strategy } from '@jackwener/opencli/registry';
import { resolveTwitterQueryId, getCt0, buildXHeaders } from './_shared/x-graphql.js';
import { extractTweetFull, detectLang } from './_shared/x-payload-parser.js';

const BOOKMARKS_QUERY_ID = 'Fy0QMy4q_aZCpkO0PnyLYw';

const BOOKMARKS_FEATURES = {
    rweb_video_screen_enabled: false,
    profile_label_improvements_pcf_label_in_post_enabled: true,
    responsive_web_profile_redirect_enabled: false,
    rweb_tipjar_consumption_enabled: false,
    verified_phone_label_enabled: false,
    creator_subscriptions_tweet_preview_api_enabled: true,
    responsive_web_graphql_timeline_navigation_enabled: true,
    responsive_web_graphql_skip_user_profile_image_extensions_enabled: false,
    premium_content_api_read_enabled: false,
    communities_web_enable_tweet_community_results_fetch: true,
    c9s_tweet_anatomy_moderator_badge_enabled: true,
    articles_preview_enabled: true,
    responsive_web_edit_tweet_api_enabled: true,
    graphql_is_translatable_rweb_tweet_is_translatable_enabled: true,
    view_counts_everywhere_api_enabled: true,
    longform_notetweets_consumption_enabled: true,
    responsive_web_twitter_article_tweet_consumption_enabled: true,
    tweet_awards_web_tipping_enabled: false,
    content_disclosure_indicator_enabled: true,
    content_disclosure_ai_generated_indicator_enabled: true,
    freedom_of_speech_not_reach_fetch_enabled: true,
    standardized_nudges_misinfo: true,
    tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled: true,
    longform_notetweets_rich_text_read_enabled: true,
    longform_notetweets_inline_media_enabled: false,
    responsive_web_enhance_cards_enabled: false,
};

function buildBookmarksUrl(queryId, count, cursor) {
    const vars = {
        count,
        includePromotedContent: false,
    };
    if (cursor) vars.cursor = cursor;
    return `/i/api/graphql/${queryId}/Bookmarks`
        + `?variables=${encodeURIComponent(JSON.stringify(vars))}`
        + `&features=${encodeURIComponent(JSON.stringify(BOOKMARKS_FEATURES))}`;
}

function parseBookmarkTweet(result, seen) {
    if (!result) return null;
    const inner = (result.__typename === 'TweetWithVisibilityResults' && result.tweet)
        ? result.tweet : (result.tweet || result);
    if (!inner?.rest_id || seen.has(inner.rest_id)) return null;
    seen.add(inner.rest_id);
    const tw = extractTweetFull(inner);
    if (!tw) return null;
    if (!tw.lang) tw.lang = detectLang(tw.text);
    return tw;
}

function parseBookmarks(data, seen) {
    const tweets = [];
    let nextCursor = null;
    const insts = data?.data?.bookmark_timeline_v2?.timeline?.instructions
        || data?.data?.bookmark_timeline?.timeline?.instructions
        || [];

    for (const inst of insts) {
        for (const entry of inst.entries || []) {
            const c = entry.content;
            if (c?.entryType === 'TimelineTimelineCursor' || c?.__typename === 'TimelineTimelineCursor') {
                if (c.cursorType === 'Bottom' || c.cursorType === 'ShowMore') nextCursor = c.value;
                continue;
            }
            if (entry.entryId?.startsWith('cursor-bottom-') || entry.entryId?.startsWith('cursor-showMore-')) {
                nextCursor = c?.value || c?.itemContent?.value || nextCursor;
                continue;
            }
            const direct = parseBookmarkTweet(c?.itemContent?.tweet_results?.result, seen);
            if (direct) {
                tweets.push(direct);
                continue;
            }
            for (const item of c?.items || []) {
                const nested = parseBookmarkTweet(item.item?.itemContent?.tweet_results?.result, seen);
                if (nested) tweets.push(nested);
            }
        }
    }
    return { tweets, nextCursor };
}

cli({
    site: 'plutus-wire',
    name: 'bookmarks',
    description: 'X bookmarks for the authenticated account via Bookmarks GraphQL',
    domain: 'x.com',
    strategy: Strategy.COOKIE,
    browser: true,
    args: [
        { name: 'limit', type: 'int', default: 80 },
    ],
    columns: ['post_id', 'author', 'posted_at', 'text', 'url',
        'likes', 'retweets', 'replies', 'views',
        'reply_count', 'quote_count', 'bookmark_count', 'thread_depth',
        'is_retweet_by', 'is_quote_of',
        'original_author', 'original_text',
        'quoted_author', 'quoted_text',
        'commentary', 'lang'],
    func: async (page, kwargs) => {
        const limit = kwargs.limit || 80;
        const t0 = Date.now();

        await page.goto('https://x.com/i/bookmarks');
        await page.wait(3);
        const ct0 = await getCt0(page);
        if (!ct0) throw new AuthRequiredError('x.com', 'no ct0 cookie');

        const queryId = await resolveTwitterQueryId(page, 'Bookmarks', BOOKMARKS_QUERY_ID);
        const headers = JSON.stringify(buildXHeaders(ct0));
        const all = [];
        const seen = new Set();
        let cursor = null;

        for (let i = 0; i < 5 && all.length < limit; i++) {
            const fetchCount = Math.min(40, limit - all.length + 10);
            const apiUrl = buildBookmarksUrl(queryId, fetchCount, cursor);
            const data = await page.evaluate(`async () => {
                const r = await fetch("${apiUrl}", { method: "GET", headers: ${headers}, credentials: 'include' });
                if (r.ok) return await r.json();
                let bodyText = '';
                try { bodyText = (await r.text()).slice(0, 800); } catch (e) {}
                return { error: r.status, body: bodyText };
            }`);
            if (data?.error) {
                if (all.length === 0) {
                    if (data.error === 401 || data.error === 403) throw new AuthRequiredError('x.com', `HTTP ${data.error}`);
                    if (data.error === 429) throw new AuthRequiredError('x.com', 'HTTP 429 rate-limited on Bookmarks');
                    throw new CommandExecutionError(
                        `HTTP ${data.error}: Bookmarks body=${(data.body || '').slice(0, 400)}`
                    );
                }
                break;
            }

            const { tweets, nextCursor } = parseBookmarks(data, seen);
            all.push(...tweets);
            if (!nextCursor || nextCursor === cursor) break;
            cursor = nextCursor;
            await page.wait(2 + Math.random() * 2);
        }

        const ranAt = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
        return [{
            source: 'bookmarks',
            feed_type: 'bookmarks',
            ran_at: ranAt,
            posts_scanned: all.length,
            latency_ms: Date.now() - t0,
            posts: all.slice(0, limit),
        }];
    },
});
