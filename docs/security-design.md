# IFSS Security Design

## Secrets and configuration

The repository contains `.env.example` with placeholders only. Developers copy it to `.env`; `.gitignore` excludes `.env` and local secret, key, certificate, data, and backup files while allowing the example template. Never hardcode credentials in source, Docker images, frontend variables, URLs, logs, or Git history. Rotate any credential that is accidentally committed; removing a file in a later commit is insufficient. In production, inject the same settings from a deployment secret store or protected environment mechanism; do not commit a production `.env`.

Use distinct least-privilege MinIO credentials per node and separate identities for API/worker/admin operations where possible. Keep OpenAI credentials server-side and grant them only to the ingestion/AI worker. Redact authorization headers and secret-valued configuration from structured logs. Rotate JWT signing keys, database passwords, MinIO keys, and provider keys on a documented schedule and immediately after suspected exposure; support key IDs and a controlled overlap window for JWT verification.

## JWT and browser sessions

- Access JWT lifetime: proposed 10 minutes; validate signature/algorithm, issuer, audience, expiry, not-before, and token purpose on every request.
- Refresh tokens: opaque high-entropy values in `Secure`, `HttpOnly`, `SameSite` cookies; store only a hash and session/family metadata in MySQL. Rotate on every refresh. Reuse of a rotated token revokes its family. Logout, password reset, account disablement, and suspected compromise revoke sessions.
- Protect cookie-authenticated state-changing requests with CSRF tokens and strict origin checks. Use HTTPS, restrictive CORS, and rate limits for login, refresh, registration, and password recovery.
- JWT signing key material is server-only; never put tokens or secrets in browser local storage by default or in URLs.

Exact refresh lifetime, key algorithm/KMS integration, password recovery, MFA, and deployment origins remain decisions for implementation review.

## CORS policy

CORS is an origin allowlist, not authentication. Reject requests from any browser origin not explicitly configured for the current environment; never use `*` or reflect arbitrary `Origin` values. With credentialed cookies enabled, wildcard origins are prohibited. Return `Vary: Origin` when responding to an allowed origin.

- **Development allowlist:** `http://localhost:5173` and `http://127.0.0.1:5173` only. Add another local origin only by explicit developer configuration.
- **Production allowlist:** exact HTTPS origins supplied through protected deployment configuration, for example `https://<approved-frontend-host>` after replacement with the actual frontend origin. No wildcard, scheme-less host, or broad subdomain pattern. Production startup must fail if the list is empty or contains a wildcard.
- **Credentials:** allowed only for the configured first-party frontend origins because the refresh token uses an HTTP-only cookie. CSRF tokens and strict Origin checks remain required for state-changing cookie-authenticated requests.
- **Allowed methods:** `GET`, `HEAD`, `POST`, `PUT`, `PATCH`, `DELETE`. The server handles CORS preflight `OPTIONS`; it is not an application data method.
- **Allowed request headers:** `Authorization`, `Content-Type`, `X-CSRF-Token`, `Idempotency-Key`, `X-Request-ID`, and `Range` for authorized media/file preview requests. For multipart upload parts, also allow `Content-Range` and `Digest`, as required by [the API contract](api-roadmap.md). Do not allow additional headers without a documented API need.
- **Exposed response headers:** `Content-Disposition`, `ETag`, `X-Request-ID`, `Accept-Ranges`, and `Content-Range` only where the browser needs to read them.

Keep development and production origin lists separate; do not ship localhost origins in production. Non-browser clients are not constrained by CORS and still require normal authentication and authorization.

## File-level authorization

Every file, file-version, job, download, chat session, chunk, summary, and search result is checked against the authenticated principal and owner (or explicit ACL if sharing is later approved). Use deny-by-default checks in the service layer; opaque IDs are not authorization. Scope SQL queries by owner before returning metadata. Search must restrict the FAISS partition to the caller and recheck chunk/file ownership in MySQL before fetching text or assembling prompts. Admin actions use a distinct role, audited routes, and preferably separate administrative access controls.

MinIO buckets are private. The API never accepts an arbitrary object key from a client. If presigned URLs are later used, authorize first and scope them to one object/version and short expiry; downloads must not bypass file state, ownership, or deletion checks.

## Uploads, AI, and network boundaries

Treat uploaded bytes, filenames, archive contents, and extracted text as hostile. Enforce actual byte quotas, MIME/content detection, parser timeouts and memory limits, archive recursion/expansion limits, safe response headers, and a malware scanning decision before public sharing. Keep MinIO, MySQL, and worker interfaces on private networks. Admin node registration must allow only approved MinIO endpoints; reject arbitrary URLs and block loopback, link-local, metadata, and unapproved private destinations to prevent SSRF.

### Query and extraction safety

- Use parameterized/prepared SQL for every value. Never interpolate client values into SQL. Identifiers that cannot be parameterized (such as sort columns or directions) must come from a fixed server-side allowlist. Use a least-privilege MySQL account and avoid dynamic SQL for owner-scoped queries.
- Run document and archive extraction in a resource-limited, non-root worker with no network access and a private temporary directory. Resolve every archive entry to a canonical path under that directory; reject absolute paths, drive prefixes, `..` traversal, symlinks/hardlinks, and any entry whose resolved path escapes the extraction root. Enforce entry-count, nesting-depth, expanded-size, compression-ratio, CPU, memory, and wall-clock limits. Clean the temporary directory on success, failure, timeout, and worker restart. Do not follow archive links or preserve executable permissions.

### Browser security headers

The frontend-serving edge must set an enforced Content Security Policy. Baseline: `default-src 'self'; script-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'`. Add only exact configured API origins to `connect-src` (including streaming); use `style-src 'self'` and nonce/hash-based exceptions if required rather than `unsafe-inline` or `unsafe-eval`. Configure image/media sources only for the preview behavior actually used. Roll out with report-only telemetry first, then enforce; do not allow arbitrary script, frame, or object sources.

Also set `X-Content-Type-Options: nosniff`, `Referrer-Policy: strict-origin-when-cross-origin`, a restrictive `Permissions-Policy`, and `X-Frame-Options: DENY` as a legacy fallback to CSP `frame-ancestors`. Enable HSTS only on HTTPS deployments after confirming the hostname policy. Markdown and filenames remain untrusted: render sanitized Markdown, never execute HTML, and encode text by output context.

Apply the app-page CSP and frame-denial headers to HTML application responses. Binary preview responses must use a media-specific policy compatible with the selected PDF viewer and remain available only through the authorized file API; do not weaken the application page policy to support previews.

Document text sent to OpenAI is an explicit data flow. Do not send files without configured policy/consent; send only required chunks, keep prompts out of logs, apply cost/rate limits, and record model/version for derived artifacts. Document retention, residency, provider settings, redaction, and opt-out policy require product approval. Treat document instructions as untrusted content in RAG.

Before production, explicitly approve whether AI processing is opt-in or opt-out, which file formats and data classifications may be sent to the provider, provider retention/residency settings, derived-data retention, and who owns consent and incident response. Finalize single-tenant versus multi-tenant operation and sharing/ACL policy before enabling shared workspaces.

## Audit and response

Audit login/session, file lifecycle, node administration, key rotation, and privileged actions with actor, outcome, entity, timestamp, and request ID; exclude secrets and document contents. Alert on repeated login failures, authorization denials, unusual download volume, node key changes, secret exposure indicators, and unexpected AI spend. Define incident response and credential revocation runbooks before production.
