# MOTGU Rank Math Read-only Bridge

This directory is the tracked source for the WordPress-side P2C2 bridge used by ContentEngine.

It is **not** activated on `motgu.com` by this change.

## Fixed read contract

The plugin exposes exactly three authenticated GET routes:

- `/wp-json/motgu-contentengine/v1/rank-math/posts/{post_id}/seo-meta`
- `/wp-json/motgu-contentengine/v1/rank-math/posts/{post_id}/schema`
- `/wp-json/motgu-contentengine/v1/rank-math/posts/{post_id}/links`

They map only to:

- `rank-math/get-post-seo-meta`
- `rank-math/get-post-schema`
- `rank-math/get-post-links`

There is no route accepting an arbitrary ability name. The bridge also checks the live Rank Math ability annotations and fails closed unless the ability remains readonly, non-destructive and idempotent.

## Authentication

Deployment requires two values outside Git:

- `MOTGU_RANK_MATH_BRIDGE_SECRET`: at least 32 characters
- `MOTGU_RANK_MATH_BRIDGE_USER_ID`: a dedicated WordPress service user ID

The HTTP caller does not receive that WordPress user's password or Application Password. The bridge authenticates the caller with HMAC-SHA256 and impersonates the dedicated user only for the bounded ability execution, then restores the previous WordPress user.

Required request headers:

- `X-MOTGU-Bridge-Timestamp`: current Unix timestamp
- `X-MOTGU-Bridge-Signature`: lowercase hex HMAC-SHA256 of:

```text
METHOD
REST_ROUTE
TIMESTAMP
```

The accepted clock skew is 300 seconds. Because all bridge routes are read-only, no nonce/replay store is added in P2C2.1. Use a different bridge secret for each environment; never reuse the local `motgu.test` secret on `motgu.com`.

The dedicated WordPress user must have only the minimum post access and the Rank Math capabilities required by the three abilities:

- `rank_math_onpage_general`
- `rank_math_onpage_snippet`
- `rank_math_link_builder`

Provisioning that user/capability assignment is an operational step and is not performed by this plugin.

## Third-party telemetry boundary

Rank Math's read abilities call its usage-tracking hook. When Rank Math usage tracking is opted in, that hook can emit a third-party telemetry event even though the SEO operation itself is read-only.

The bridge therefore fails closed with `rank_math_tracking_enabled` while Rank Math usage tracking is opted in. It does **not** change the Rank Math preference. Production activation must decide explicitly whether this bridge is compatible with the site's tracking preference; P2C2.1 does not make that decision for `motgu.com`.

## Output boundary

Every response includes:

- payload schema version
- source and upstream source
- exact Rank Math ability name
- WordPress post ID
- WordPress permalink/status/modified-GMT identity
- Rank Math Free/PRO version metadata
- capture timestamp
- `safe_data`

Top-level Rank Math output is allowlisted per ability. Unknown top-level fields are discarded. Nested Schema payloads are bounded, JSON-only, and rejected if a secret-shaped key is encountered. Link output is bounded to 1000 items and the sanitized payload is capped at 512 KiB.

The bridge never returns OAuth/access/refresh tokens, cookies, authorization headers, passwords, credentials or raw settings blobs.

## Non-goals

P2C2.1 does not:

- publish or edit WordPress content;
- change Rank Math settings/modules;
- expose the generic MCP executor;
- read Search Console or Google Analytics metrics;
- add AI Visibility, 404 or top-keyword access;
- persist a ContentEngine Artifact;
- activate production configuration.

ContentEngine identity/version validation and immutable Artifact capture belong to P2C2.2/P2C2.3.

## Local contract test

```sh
php -l wordpress/motgu-rank-math-bridge/motgu-rank-math-bridge.php
php -l wordpress/motgu-rank-math-bridge/src/Bridge.php
php wordpress/motgu-rank-math-bridge/tests/contract-test.php
```

Expected final line:

`PASS_P2C21_BRIDGE_CONTRACT`