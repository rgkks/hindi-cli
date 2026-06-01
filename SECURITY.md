# Security Policy

## Supported Versions

| Version | Supported          |
|---------|-------------------|
| Beta 1.x | ✅ Fully supported |

## Reporting a Vulnerability

hindi-cli relies on external dependencies (`yt-dlp`, `mpv`, `fzf`) and does not handle sensitive user data beyond local watch history. However, if you discover a security vulnerability:

1. **Do not** open a public GitHub issue.
2. Email the maintainers directly or open a draft security advisory on GitHub.
3. We will respond within 48 hours and coordinate a fix.

## Best Practices

- Always install hindi-cli from the official GitHub repository
- Keep dependencies updated (`pip install --upgrade yt-dlp`)
- Review any third-party plugins before enabling them
- The config file stores only user preferences (no secrets or credentials)
