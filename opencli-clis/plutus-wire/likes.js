// Plutus Wire likes — COOKIE strategy. Fetches liked tweets for a user-selected
// account via X LikedTweets GraphQL. Read-only; never triggers write actions.
//
// Output shape: SAME as timeline.js + user-tweets.js (posts array) so
// Plutus Wire ingest can parse it with the same contract as timeline output.
//
// Pagination: infinite scroll up to `limit` posts across at most 10 pages.
// Each page fetches ~20 items; limit default=200 matches FIRST_RUN_HARD_CAP.
//
// Auth notes:
//   - Uses the user's logged-in browser session
//   - ct0 cookie required (same as all X GraphQL calls)
//   - LikedTweets endpoint: GET /i/api/graphql/<queryId>/LikedTweets

import { AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors';
import { cli, Strategy } from '@jackwener/opencli/registry';
import { resolveTwitterQueryId, getCt0, buildXHeaders } from './_shared/x-graphql.js';
import { extractTweetFull, extractRetweetEvent, detectLang } from './_shared/x-payload-parser.js';

// QueryId fallbacks (X rotates weekly; resolveTwitterQueryId fetches live id first).
// Fallback query ids rotate; resolveTwitterQueryId fetches live ids first.
const USER_BY_SCREEN_NAME_QUERY_ID = '1VOOyvKkiI3FMmkeDNxM9A';
const LIKED_TWEETS_QUERY_ID        = 'a2vYKkx2AtoCmEIRO8Gfbw';  // refreshed 2026-04-21

// fieldToggles aligned with the working local adapter snapshot.
const FIELD_TOGGLES = {
    withPayments: false,
    withAuxiliaryUserLabels: true,
    withArticleRichContentState: true,
    withArticlePlainText: true,
    withArticleSummaryText: true,
    withArticleVoiceOver: false,
    withGrokAnalyze: false,
    withDisallowedReplyControls: false,
};

// Likes uses a different feature payload than generic timeline ops.
const LIKES_FEATURES = {
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
    responsive_web_grok_analyze_button_fetch_trends_enabled: false,
    responsive_web_grok_analyze_post_followups_enabled: false,
    responsive_web_jetfuel_frame: true,
    responsive_web_grok_share_attachment_enabled: true,
    responsive_web_grok_annotations_enabled: true,
    articles_preview_enabled: true,
    responsive_web_edit_tweet_api_enabled: true,
    graphql_is_translatable_rweb_tweet_is_translatable_enabled: true,
    view_counts_everywhere_api_enabled: true,
    longform_notetweets_consumption_enabled: true,
    responsive_web_twitter_article_tweet_consumption_enabled: true,
    tweet_awards_web_tipping_enabled: false,
    content_disclosure_indicator_enabled: true,
    content_disclosure_ai_generated_indicator_enabled: true,
    responsive_web_grok_show_grok_translated_post: false,
    responsive_web_grok_analysis_button_from_backend: true,
    post_ctas_fetch_enabled: false,
    freedom_of_speech_not_reach_fetch_enabled: true,
    standardized_nudges_misinfo: true,
    tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled: true,
    longform_notetweets_rich_text_read_enabled: true,
    longform_notetweets_inline_media_enabled: false,
    responsive_web_grok_image_annotation_enabled: true,
    responsive_web_grok_imagine_annotation_enabled: true,
    responsive_web_grok_community_note_auto_translation_is_enabled: false,
    responsive_web_enhance_cards_enabled: false,
};

async function resolveUserId(page, ct0, handle) {
    const queryId = await resolveTwitterQueryId(page, 'UserByScreenName', USER_BY_SCREEN_NAME_QUERY_ID);
    const headers = JSON.stringify(buildXHeaders(ct0));
    const result = await page.evaluate(`async () => {
      const variables = JSON.stringify({ screen_name: ${JSON.stringify(handle)}, withSafetyModeUserFields: true });
      const features = JSON.stringify({
        hidden_profile_subscriptions_enabled: true,
        rweb_tipjar_consumption_enabled: true,
        responsive_web_graphql_exclude_directive_enabled: true,
        verified_phone_label_enabled: false,
        subscriptions_verification_info_is_identity_verified_enabled: true,
        subscriptions_verification_info_verified_since_enabled: true,
        highlights_tweets_tab_ui_enabled: true,
        responsive_web_twitter_article_notes_tab_enabled: true,
        subscriptions_feature_can_gift_premium: true,
        creator_subscriptions_tweet_preview_api_enabled: true,
        responsive_web_graphql_skip_user_profile_image_extensions_enabled: false,
        responsive_web_graphql_timeline_navigation_enabled: true,
      });
      const url = '/i/api/graphql/' + ${JSON.stringify(queryId)} + '/UserByScreenName?variables='
        + encodeURIComponent(variables) + '&features=' + encodeURIComponent(features);
      const resp = await fetch(url, { headers: ${headers}, credentials: 'include' });
      if (!resp.ok) return { error: 'HTTP ' + resp.status };
      const d = await resp.json();
      const r = d.data?.user?.result;
      if (!r) return { error: 'no user' };
      return { rest_id: r.rest_id || null };
    }`);
    if (result?.error) throw new CommandExecutionError(`UserByScreenName(${handle}): ${result.error}`);
    if (!result?.rest_id) throw new CommandExecutionError(`UserByScreenName(${handle}): missing rest_id`);
    return result.rest_id;
}

function buildLikedTweetsUrl(queryId, userId, count, cursor) {
    const vars = {
        userId,
        count,
        includePromotedContent: false,
        withClientEventToken: false,
        withBirdwatchNotes: false,
        withVoice: true,
        withV2Timeline: true,
    };
    if (cursor) vars.cursor = cursor;
    // Operation name is "Likes" for the refreshed query id.
    return `/i/api/graphql/${queryId}/Likes`
        + `?variables=${encodeURIComponent(JSON.stringify(vars))}`
        + `&features=${encodeURIComponent(JSON.stringify(LIKES_FEATURES))}`
        + `&fieldToggles=${encodeURIComponent(JSON.stringify(FIELD_TOGGLES))}`;
}

function parseLikedTweets(data, seen) {
    const tweets = [];
    let nextCursor = null;

    // LikedTweets response path mirrors UserTweets structure
    const insts = data?.data?.user?.result?.timeline_v2?.timeline?.instructions
        || data?.data?.user?.result?.timeline?.timeline?.instructions
        || [];

    for (const inst of insts) {
        for (const entry of inst.entries || []) {
            const c = entry.content;
            if (c?.entryType === 'TimelineTimelineCursor' || c?.__typename === 'TimelineTimelineCursor') {
                if (c.cursorType === 'Bottom') nextCursor = c.value;
                continue;
            }
            const tweetResult = c?.itemContent?.tweet_results?.result;
            if (!tweetResult) continue;
            if (c?.itemContent?.promotedMetadata) continue;
            const inner = (tweetResult.__typename === 'TweetWithVisibilityResults' && tweetResult.tweet)
                ? tweetResult.tweet : tweetResult;
            if (!inner.rest_id || seen.has(inner.rest_id)) continue;
            seen.add(inner.rest_id);
            const rtEvt = extractRetweetEvent(c);
            const tw = extractTweetFull(inner, {
                is_retweet_by: rtEvt?.retweeter_handle || null,
            });
            if (tw) {
                if (!tw.lang) tw.lang = detectLang(tw.text);
                tweets.push(tw);
            }
        }
    }
    return { tweets, nextCursor };
}

cli({
    site: 'plutus-wire',
    name: 'likes',
    description: 'X LikedTweets for an account via LikedTweets GraphQL (read-only)',
    domain: 'x.com',
    strategy: Strategy.COOKIE,
    browser: true,
    args: [
        { name: 'handle', type: 'string', required: true },
        { name: 'limit',  type: 'int',    default: 200 },
    ],
    columns: ['post_id', 'author', 'posted_at', 'text', 'url',
        'likes', 'retweets', 'replies', 'views',
        'reply_count', 'quote_count', 'bookmark_count', 'thread_depth',
        'is_retweet_by', 'is_quote_of',
        'original_author', 'original_text',
        'quoted_author', 'quoted_text',
        'commentary', 'lang'],
    func: async (page, kwargs) => {
        const handle = String(kwargs.handle || '').replace(/^@/, '');
        if (!handle) throw new CommandExecutionError('--handle is required');
        const limit = kwargs.limit || 200;

        const t0 = Date.now();

        // Warm up cookies by landing on the likes page directly.
        await page.goto(`https://x.com/${handle}/likes`);
        await page.wait(4);  // allow session + ct0 cookie to settle
        const ct0 = await getCt0(page);
        if (!ct0) throw new AuthRequiredError('x.com', 'no ct0 cookie — re-login required');

        const userId = await resolveUserId(page, ct0, handle);
        const queryId = await resolveTwitterQueryId(page, 'LikedTweets', LIKED_TWEETS_QUERY_ID);
        const headers = JSON.stringify(buildXHeaders(ct0));

        const all = [];
        const seen = new Set();
        let cursor = null;

        // Up to 10 pages × ~20 posts each = 200 max (matches FIRST_RUN_HARD_CAP)
        for (let pageNum = 0; pageNum < 10 && all.length < limit; pageNum++) {
            const fetchCount = Math.min(20, limit - all.length + 5);
            const apiUrl = buildLikedTweetsUrl(queryId, userId, fetchCount, cursor);

            const data = await page.evaluate(`async () => {
                const r = await fetch("${apiUrl}", { method: "GET", headers: ${headers}, credentials: 'include' });
                if (r.ok) return await r.json();
                let bodyText = '';
                try { bodyText = (await r.text()).slice(0, 800); } catch (e) {}
                return { error: r.status, body: bodyText };
            }`);
            if (data?.error) console.error('[likes-debug]', data.error, data.body || '');

            if (data?.error) {
                if (all.length === 0) {
                    if (data.error === 401 || data.error === 403) throw new AuthRequiredError('x.com', `HTTP ${data.error}`);
                    if (data.error === 429) throw new AuthRequiredError('x.com', 'HTTP 429 rate-limited on LikedTweets');
                    throw new CommandExecutionError(
                        `HTTP ${data.error}: LikedTweets(@${handle}) body=${(data.body || '').slice(0, 400)}`
                    );
                }
                break;  // partial data ok — stop pagination
            }

            const { tweets, nextCursor } = parseLikedTweets(data, seen);
            all.push(...tweets);

            if (!nextCursor || nextCursor === cursor) break;  // end of feed
            cursor = nextCursor;

            // Small wait between pages to avoid rate limits (gamma 2-4s)
            await page.wait(2 + Math.random() * 2);
        }

        const ranAt = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
        return [{
            source:       'likes',
            feed_type:    'likes',
            handle,
            user_id:      userId,
            ran_at:       ranAt,
            posts_scanned: all.length,
            latency_ms:   Date.now() - t0,
            posts:        all.slice(0, limit),
        }];
    },
});
