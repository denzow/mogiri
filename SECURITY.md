# Security Policy

## Design Philosophy

mogiri is designed as a **localhost-only** tool. By default it binds to `127.0.0.1:8899`, which means only processes on the same machine can reach it. This is the primary security boundary.

Since mogiri can execute arbitrary shell commands and Python scripts, **network access to mogiri is equivalent to shell access**. This is intentional within the localhost trust boundary.

## Protections

### CSRF Protection (Web UI)

All state-changing requests through the Web UI (POST, PUT, PATCH, DELETE) are protected by CSRF tokens via Flask-WTF. This prevents cross-site attacks such as DNS rebinding from triggering job execution through a user's browser.

### API Token Authentication (REST API)

The `/api/*` endpoints require a Bearer token in the `Authorization` header. A random token is auto-generated on first startup and stored at `~/.mogiri/api_token`. The `mogiricli` CLI reads this token automatically.

To disable authentication (e.g., for backward compatibility), set in `config.yaml`:

```yaml
auth:
  enabled: false
```

### Password Authentication (Web UI)

When `auth.password` is set in `config.yaml` (or `MOGIRI_PASSWORD` environment variable), the Web UI requires password login. A session cookie is set after successful authentication.

**Binding to non-localhost addresses (e.g., `--host 0.0.0.0`) requires a password to be configured.** mogiri will refuse to start without one.

```yaml
auth:
  password: "your-password-here"
```

### SECRET_KEY

Flask session signing uses `SECRET_KEY`. Set the `MOGIRI_SECRET_KEY` environment variable for production use. The default key is intended only for local development.

## Risk of `--host 0.0.0.0`

Running `mogiri serve --host 0.0.0.0` exposes the server to **all network interfaces**. Any device on the same network (or the internet, depending on firewall rules) can access mogiri's UI and API. Since mogiri can execute arbitrary shell commands, this is extremely dangerous without additional network-level protections (firewall, VPN, reverse proxy with authentication).

mogiri requires `auth.password` to be configured before allowing non-localhost binding. This ensures the Web UI is always password-protected when exposed to the network. API endpoints are additionally protected by Bearer token authentication.

**Recommendation**: Only bind to `0.0.0.0` if you understand the risks and have appropriate network controls in place.

## Reporting Vulnerabilities

If you discover a security vulnerability, please report it by opening a GitHub issue or contacting the maintainer directly.

Since mogiri is a localhost tool, most "vulnerabilities" are expected behaviors within the trust boundary. However, reports of issues like CSRF bypasses, token leaks, or authentication bypasses are welcome.
