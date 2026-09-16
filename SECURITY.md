# Security notes

PT Zero is an educational synthetic-data MVP. Do not enter real health or
identifying information.

Implemented controls:

- Argon2 password hashing through `pwdlib`
- Uniform password verification path for unknown accounts
- Opaque random session IDs stored as SHA-256 digests
- Eight-hour revocable server-side sessions
- `HttpOnly` session cookies and `SameSite=Strict`
- `Secure` cookies and HSTS when `COOKIE_SECURE=true`
- Separate CSRF cookie/header with a server-side digest
- No-store API responses
- CSP, frame denial, MIME sniffing, referrer, and browser-permission headers
- Passwords and raw session tokens are never stored in the database

Known MVP limitations:

- No account verification, recovery, MFA, or administrative roles
- No distributed rate limiting or brute-force protection
- SQLite is not suitable for horizontally scaled authentication
- No external secret manager or managed identity provider
- Local HTTP intentionally disables the `Secure` cookie flag

For a real deployment, prefer a reviewed identity provider using OAuth 2.0/OpenID
Connect and managed persistent storage. Report security issues privately rather
than opening a public issue containing exploit details.

