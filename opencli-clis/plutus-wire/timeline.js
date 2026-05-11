// Plutus Wire timeline — COOKIE strategy. Reads the user's own visible X home
// timeline sources through OpenCLI's browser bridge.

import { AuthRequiredError, CommandExecutionError } from '@jackwener/opencli/errors';
import { cli, Strategy } from '@jackwener/opencli/registry';
import { resolveTwitterQueryId, getCt0, getXFeatures, buildXHeaders } from './_shared/x-graphql.js';
import { extractTweetFull, extractRetweetEvent, detectLang } from './_shared/x-payload-parser.js';

const HOME_TIMELINE_QUERY_ID = 'c-CzHF1LboFilMpsx4ZCrQ';
const HOME_LATEST_TIMELINE_QUERY_ID = 'BKB7oi212Fi7kQtCBGE4zA';
const AI_HOME_TAB = {
    tag: '1925953013547450368',
    topicIds: ['-42', '-1925952771733262336', '-1000000000000000004', '-1925949693290295298'],
};

const ENDPOINTS = {
    'for-you': { endpoint: 'HomeTimeline', method: 'GET', fallback: HOME_TIMELINE_QUERY_ID },
    ai: { endpoint: 'HomeTimeline', method: 'GET', fallback: HOME_TIMELINE_QUERY_ID },
    following: { endpoint: 'HomeLatestTimeline', method: 'POST', fallback: HOME_LATEST_TIMELINE_QUERY_ID },
};

function buildVariables(type, count, cursor) {
    if (type === 'ai') {
        const v = {
            count,
            includePromotedContent: true,
            requestContext: 'launch',
            tag: AI_HOME_TAB.tag,
            topicIds: AI_HOME_TAB.topicIds,
            withCommunity: true,
        };
        if (cursor) v.cursor = cursor;
        return v;
    }
    const v = { count, includePromotedContent: false, latestControlAvailable: true, requestContext: 'launch' };
    if (type === 'for-you') v.withCommunity = true;
    if (type === 'following') v.seenTweetIds = [];
    if (cursor) v.cursor = cursor;
    return v;
}

function buildUrl(queryId, endpoint, vars) {
    return `/i/api/graphql/${queryId}/${endpoint}`
        + `?variables=${encodeURIComponent(JSON.stringify(vars))}`
        + `&features=${encodeURIComponent(JSON.stringify(getXFeatures()))}`;
}

function parseHomeTimeline(data, seen) {
    const tweets = [];
    const retweetEvents = [];
    let nextCursor = null;
    const insts = data?.data?.home?.home_timeline_urt?.instructions || [];
    for (const inst of insts) {
        for (const entry of inst.entries || []) {
            const c = entry.content;
            if (c?.entryType === 'TimelineTimelineCursor' || c?.__typename === 'TimelineTimelineCursor') {
                if (c.cursorType === 'Bottom') nextCursor = c.value;
                continue;
            }
            const tweetResult = c?.itemContent?.tweet_results?.result;
            if (tweetResult) {
                if (c?.itemContent?.promotedMetadata) continue;
                const inner = (tweetResult.__typename === 'TweetWithVisibilityResults' && tweetResult.tweet)
                    ? tweetResult.tweet : tweetResult;
                if (!inner.rest_id || seen.has(inner.rest_id)) continue;
                seen.add(inner.rest_id);
                const tw = extractTweetFull(inner);
                if (tw) {
                    if (!tw.lang) tw.lang = detectLang(tw.text);
                    tweets.push(tw);
                }
                const evt = extractRetweetEvent(c?.itemContent, inner);
                if (evt) retweetEvents.push(evt);
                continue;
            }
            for (const item of c?.items || []) {
                const nested = item.item?.itemContent?.tweet_results?.result;
                if (!nested) continue;
                if (item.item?.itemContent?.promotedMetadata) continue;
                const inner = (nested.__typename === 'TweetWithVisibilityResults' && nested.tweet) ? nested.tweet : nested;
                if (!inner.rest_id || seen.has(inner.rest_id)) continue;
                seen.add(inner.rest_id);
                const tw = extractTweetFull(inner);
                if (tw) {
                    if (!tw.lang) tw.lang = detectLang(tw.text);
                    tweets.push(tw);
                }
            }
        }
    }
    return { tweets, retweetEvents, nextCursor };
}

cli({
    site: 'plutus-wire',
    name: 'timeline',
    description: 'X home timeline (following, for-you, or AI topic tab)',
    domain: 'x.com',
    strategy: Strategy.COOKIE,
    browser: true,
    args: [
        { name: 'type', type: 'string', default: 'for-you', choices: ['for-you', 'following', 'ai'] },
        { name: 'limit', type: 'int', default: 50 },
    ],
    columns: ['post_id', 'author', 'posted_at', 'text', 'url',
        'likes', 'retweets', 'replies', 'views',
        'is_retweet_by', 'is_quote_of', 'original_author', 'commentary', 'lang'],
    func: async (page, kwargs) => {
        const type = kwargs.type === 'following' ? 'following' : (kwargs.type === 'ai' ? 'ai' : 'for-you');
        const limit = kwargs.limit || 50;
        const { endpoint, method, fallback } = ENDPOINTS[type];
        const t0 = Date.now();

        await page.goto('https://x.com');
        await page.wait(3);
        const ct0 = await getCt0(page);
        if (!ct0) throw new AuthRequiredError('x.com', 'no ct0 cookie');

        const queryId = await resolveTwitterQueryId(page, endpoint, fallback);
        const headers = JSON.stringify(buildXHeaders(ct0));

        const all = [];
        const allRetweetEvents = [];
        const seen = new Set();
        let cursor = null;
        for (let i = 0; i < 5 && all.length < limit; i++) {
            const perPage = type === 'ai' ? 20 : 40;
            const fetchCount = Math.min(perPage, limit - all.length + 5);
            const vars = buildVariables(type, fetchCount, cursor);
            const apiUrl = buildUrl(queryId, endpoint, vars);
            const data = await page.evaluate(`async () => {
                const r = await fetch("${apiUrl}", { method: "${method}", headers: ${headers}, credentials: 'include' });
                return r.ok ? await r.json() : { error: r.status };
            }`);
            if (data?.error) {
                if (all.length === 0) {
                    if (data.error === 401 || data.error === 403) throw new AuthRequiredError('x.com', `HTTP ${data.error}`);
                    if (data.error === 429) throw new AuthRequiredError('x.com', 'HTTP 429 rate-limited');
                    throw new CommandExecutionError(`HTTP ${data.error}: HomeTimeline (queryId may have rotated)`);
                }
                break;
            }
            const { tweets, retweetEvents, nextCursor } = parseHomeTimeline(data, seen);
            all.push(...tweets);
            allRetweetEvents.push(...retweetEvents);
            if (!nextCursor || nextCursor === cursor) break;
            cursor = nextCursor;
        }

        const ranAt = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
        return [{
            source: type,
            feed_type: type,
            ran_at: ranAt,
            posts_scanned: all.length,
            latency_ms: Date.now() - t0,
            posts: all.slice(0, limit),
            retweet_events: allRetweetEvents,
        }];
    },
});
