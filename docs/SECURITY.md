# Security Posture

This service implements multiple layered controls to reduce the likelihood and
impact of common web application threats. The following table summarises the
primary mitigations and the threats they address.

| Control | Threats Mitigated |
| --- | --- |
| HTTPS enforcement | Man-in-the-middle attacks, credential interception |
| Vault-backed secret retrieval | Secret sprawl, configuration leaks |
| Request rate limiting | Credential stuffing, brute force, API abuse |
| Structured audit logging | Non-repudiation, incident response gaps |
| Input sanitisation | Cross-site scripting (XSS), reflected injection |
| Encryption at rest | Database snapshot leakage, insider risk |

## Transport security

`HTTPSRedirectMiddleware` is registered globally to ensure all HTTP requests are
redirected to HTTPS. The application should still be deployed behind a TLS
terminating proxy or gateway; the middleware adds defence in depth and protects
misconfigured upstream components.

## Secrets management

Secrets, including the symmetric encryption key, are retrieved via a
`VaultClient` wrapper around HashiCorp Vault. In environments where Vault is not
available, deterministic environment variable fallbacks are used. This design
keeps the bootstrap path simple while enabling production-grade secret
management.

Configuration environment variables:

- `VAULT_ADDR`, `VAULT_TOKEN`, `VAULT_VERIFY`
- `VAULT_SECRET_PATH`
- `VAULT_ENCRYPTION_KEY_FIELD`
- `ENCRYPTION_KEY` (fallback, intended for local development)

## Rate limiting

An in-memory fixed-window rate limiter guards every request. Defaults can be
adjusted via `RATE_LIMIT_MAX_REQUESTS` and `RATE_LIMIT_WINDOW_SECONDS`. The
middleware communicates quota metadata through `X-RateLimit-*` headers and
returns RFC-compliant `Retry-After` guidance when limits are exceeded.

## Audit logging

All requests are recorded through a dedicated `app.audit` logger. Logs are
formatted as structured JSON with latency, client, method, and status code
metadata to support forensics and anomaly detection. Log rotation is handled via
`TimedRotatingFileHandler`. The log path is configurable via `AUDIT_LOG_PATH`.

## Input sanitisation

Payloads are sanitised centrally using `bleach` before Pydantic validation. A
middleware layer also cleans query parameters to mitigate reflected injection
and XSS vectors. Sanitisation removes unsafe tags, attributes, and JavaScript
protocols while preserving legitimate text content.

## Encryption at rest

Item descriptions are encrypted transparently using a cached `DataEncryptor`
wrapper around the Fernet symmetric cipher. Only decrypted values are returned
to API consumers, while ciphertext is persisted to the database, reducing the
risk of data exposure through backups or insider threats.

## OWASP Top Ten alignment

- **A01: Broken Access Control** – request throttling discourages brute force
  and credential stuffing.
- **A02: Cryptographic Failures** – enforced HTTPS and Fernet encryption protect
  data in transit and at rest.
- **A03: Injection** – sanitisation is applied to inputs and query parameters.
- **A07: Identification and Authentication Failures** – audit trails assist with
  monitoring and incident response.
- **A09: Security Logging and Monitoring Failures** – structured audit logging
  captures request metadata for anomaly detection.

See the application `README.md` for operational guidance on configuring these
controls.
