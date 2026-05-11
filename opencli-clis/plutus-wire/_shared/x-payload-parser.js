// Tweet / Grok payload parsers.
// Output of extractTweetFull is the Plutus Wire JSON adapter contract.

// X GraphQL legacy.created_at is in Twitter format ("Fri Apr 17 04:30:29 +0000 2026"),
// not ISO8601. Convert so SQLite datetime() / ORDER BY work and posts.posted_at
// matches the format other ingestors write.
function twitterTimeToISO8601(s) {
    if (!s || typeof s !== 'string') return '';
    // Already ISO8601? leave alone.
    if (/^\d{4}-\d{2}-\d{2}T/.test(s)) return s;
    const d = new Date(s);
    if (isNaN(d.getTime())) return s;  // unparseable — return raw so we can debug
    return d.toISOString().replace(/\.\d{3}Z$/, 'Z');
}

// from upstream clis/twitter/timeline.js extractTweet — extended for
// retweet wrapping (TweetWithVisibilityResults), quote payload (quoted_status_result),
// and is_retweet_by detection from social_context.
export function extractTweetFull(rawTweet, opts = {}) {
    if (!rawTweet) return null;

    // Unwrap TweetWithVisibilityResults — same shape gotcha upstream search.js handles.
    let tw = rawTweet.tweet || rawTweet;
    if (tw.__typename === 'TweetWithVisibilityResults' && tw.tweet) {
        tw = tw.tweet;
    }
    if (!tw.rest_id) return null;

    const l = tw.legacy || {};
    const u = tw.core?.user_results?.result;
    // X moved screen_name from legacy to core mid-2026 — try both.
    const screenName = u?.core?.screen_name || u?.legacy?.screen_name || 'unknown';

    // Long-form notes overflow legacy.full_text (280-char ceiling); prefer note_tweet.
    const noteText = tw.note_tweet?.note_tweet_results?.result?.text;
    const text = noteText || l.full_text || '';

    // X returns views.count as a string ("12345") — coerce.
    const views = tw.views?.count ? parseInt(tw.views.count, 10) : 0;

    // Velocity / signal fields (subagent C 2026-04-17).
    // reply_count + quote_count + bookmark_count enable the "viral burst"
    // detector + downstream score_clusters.py weighting. thread_depth=1 when
    // post is a reply (in_reply_to_status_id_str set), 0 otherwise — cheap
    // proxy for "is this part of a thread" without a second TweetDetail call.
    const replyCount = l.reply_count != null ? l.reply_count : 0;
    const quoteCount = l.quote_count != null ? l.quote_count : 0;
    const bookmarkCount = l.bookmark_count != null ? l.bookmark_count : 0;
    const threadDepth = l.in_reply_to_status_id_str ? 1 : 0;

    // Detect retweet: legacy.retweeted_status_result exists when this entry is
    // X reposting Y. is_retweet_by = the reposter's handle (passed in opts
    // because the rawTweet IS the original — the reposter handle lives one
    // entry up the timeline tree).
    const retweetInner = l.retweeted_status_result?.result;
    const isRetweetBy = opts.is_retweet_by || (retweetInner ? screenName : null);

    // Detect quote: quoted_status_result lives on the wrapper.
    const quoted = tw.quoted_status_result?.result;
    let isQuoteOf = null;
    let originalAuthor = null;
    let originalText = null;
    let quotedAuthor = null;
    let commentary = null;
    let quotedText = null;
    if (quoted) {
        const qInner = quoted.tweet || quoted;
        isQuoteOf = qInner.rest_id || null;
        const qu = qInner.core?.user_results?.result;
        quotedAuthor = qu?.core?.screen_name || qu?.legacy?.screen_name || null;
        originalAuthor = quotedAuthor;  // backward-compatible alias used by older ingestors
        // For quote tweets, this tweet's text IS the commentary on the quoted.
        commentary = text || null;
        // Pull the quoted post's body so downstream sees actual content even when
        // commentary is empty/emoji-only. Long-form lives in note_tweet on the
        // quoted entry, mirror the main-text fallback chain above.
        const qLegacy = qInner.legacy || {};
        const qNoteText = qInner.note_tweet?.note_tweet_results?.result?.text;
        quotedText = (qNoteText || qLegacy.full_text || qLegacy.text || '').trim() || null;
    } else if (retweetInner) {
        // Pure retweet — original_author is the inner author.
        const rInner = retweetInner.tweet || retweetInner;
        const ru = rInner.core?.user_results?.result;
        originalAuthor = ru?.core?.screen_name || ru?.legacy?.screen_name || null;
        const rLegacy = rInner.legacy || {};
        const rNoteText = rInner.note_tweet?.note_tweet_results?.result?.text;
        originalText = (rNoteText || rLegacy.full_text || rLegacy.text || '').trim() || null;
    }

    return {
        post_id: tw.rest_id,
        author: screenName,
        posted_at: twitterTimeToISO8601(l.created_at || ''),
        text,
        url: `https://x.com/${screenName}/status/${tw.rest_id}`,
        likes: l.favorite_count || 0,
        retweets: l.retweet_count || 0,
        replies: l.reply_count || 0,
        views,
        // velocity fields (subagent C 2026-04-17)
        reply_count: replyCount,
        quote_count: quoteCount,
        bookmark_count: bookmarkCount,
        thread_depth: threadDepth,
        is_retweet_by: isRetweetBy,
        is_quote_of: isQuoteOf,
        original_author: originalAuthor,
        original_text: originalText,
        quoted_author: quotedAuthor,
        commentary,
        quoted_text: quotedText,
        lang: l.lang || detectLang(text),
    };
}

// Grok response is delivered as plain assistant text in the last message
// bubble; our prompts (grok_sweep_*.md) instruct it to emit a single JSON
// array. Strip code fences if present, then JSON.parse — throw on failure
// so orchestrate_grok_sweep.py can mark the sweep failed and retry.
export function extractGrokResponse(rawText) {
    if (!rawText || typeof rawText !== 'string') {
        throw new Error('grok_empty_response');
    }
    let cleaned = rawText.trim();
    // Strip ```json ... ``` or ``` ... ``` fences Grok sometimes adds despite prompt.
    cleaned = cleaned.replace(/^```(?:json)?\s*/i, '').replace(/\s*```\s*$/, '');
    // Find the first array bracket — Grok occasionally prefaces with "Here is the JSON:".
    const arrStart = cleaned.indexOf('[');
    const arrEnd = cleaned.lastIndexOf(']');
    if (arrStart === -1 || arrEnd === -1 || arrEnd < arrStart) {
        throw new Error('grok_no_array_found');
    }
    const sliced = cleaned.slice(arrStart, arrEnd + 1);
    try {
        const parsed = JSON.parse(sliced);
        if (!Array.isArray(parsed)) throw new Error('grok_not_array');
        return parsed;
    } catch (e) {
        throw new Error(`grok_parse_failed: ${e.message}`);
    }
}

// CJK unicode block test — matches scripts/ingest_grok_sweep.py L24-25 has_cjk
// so lang is consistent across the JS adapter and Python ingest.
export function detectLang(text) {
    return /[\u4e00-\u9fff]/.test(text || '') ? 'zh' : 'en';
}

// Pull a retweet event from a single timeline GraphQL entry. Timeline entries
// for retweets carry socialContext.contextType === 'Retweeted' on the entry's
// itemContent; the inner tweet is the ORIGINAL post (not the retweet shell).
// Returns null when entry is not a retweet event.
export function extractRetweetEvent(rawEntry) {
    if (!rawEntry) return null;
    const itemContent = rawEntry.content?.itemContent || rawEntry.itemContent;
    if (!itemContent) return null;

    const ctx = itemContent.socialContext;
    if (!ctx || ctx.contextType !== 'Retweeted') return null;

    const tweetResult = itemContent.tweet_results?.result;
    if (!tweetResult) return null;
    let tw = tweetResult.tweet || tweetResult;
    if (tw.__typename === 'TweetWithVisibilityResults' && tw.tweet) tw = tw.tweet;
    if (!tw.rest_id) return null;

    // socialContext.text is "X reposted" / "X 已转贴"; the actual handle lives
    // in the entry's user_results when present, otherwise we fall back to
    // parsing the localized text — leave that to ingest if both fail.
    const retweeterUser = itemContent.user_results?.result
        || rawEntry.content?.user_results?.result
        || null;
    const retweeterHandle = retweeterUser?.core?.screen_name
        || retweeterUser?.legacy?.screen_name
        || null;

    return {
        retweeter_handle: retweeterHandle,
        original_post_id: tw.rest_id,
        // Timeline entries don't carry the retweet timestamp directly; best we
        // have is "now" at observation time — caller stamps it.
        retweeted_at: null,
    };
}
