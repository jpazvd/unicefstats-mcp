# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| 0.3.x   | Yes       |
| < 0.3   | No        |

## Reporting a Vulnerability

If you discover a security vulnerability in unicefstats-mcp, please report it responsibly:

1. **Do not** open a public GitHub issue for security vulnerabilities
2. Email the maintainer at the address listed in [pyproject.toml](pyproject.toml)
3. Include a description of the vulnerability, steps to reproduce, and potential impact
4. Allow up to 7 days for an initial response

## Scope

This MCP server:
- Makes read-only queries to the public UNICEF SDMX API (no authentication required)
- Does not store user data, credentials, or API keys
- Does not modify any external systems
- Runs locally via stdio or as an SSE server on a user-specified port

## Known Security Considerations

- **No input sanitization for SDMX queries**: User-provided indicator codes and country codes are passed to the UNICEF SDMX API. The API itself validates inputs, but malformed inputs could trigger unexpected API responses.
- **SSE transport**: When running with `--transport sse`, the server listens on a network port. Use appropriate firewall rules and do not expose to the public internet without authentication.
- **Dependencies**: This package depends on `fastmcp` and `unicefdata`. Monitor these for security advisories.

## Provenance

- All releases are published to PyPI from GitHub Actions via Trusted Publishing (OIDC)
- Source code is available at https://github.com/jpazvd/unicefstats-mcp
- The package is maintained by Joao Pedro Azevedo (`jpazvd`)
