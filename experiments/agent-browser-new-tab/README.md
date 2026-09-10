# agent-browser: the first request in a new tab

Automated local test prepared with Codex on September 10, 2026. It compares the official **0.36.0 and 0.37.0** releases against a small HTTP server, using the same Chromium and fresh browser profiles.

| First GET | 0.36.0 | 0.37.0 |
|---|---|---|
| Main tab | Custom User-Agent and X-Global present | Both present |
| New tab | Default User-Agent; X-Global missing | Both configured values present |

The server records the request before responding. The test opens each route once, without reloading. The included script passed all 20 CLI commands; its run took 6.118 seconds.

## Reproduce

Requires macOS on Apple Silicon, Python 3.9+, curl and a separate Chromium for Testing executable. Set CHROMIUM_PRUEBAS to that executable, then run:

```sh
python3 reproduce.py --chromium-path "$CHROMIUM_PRUEBAS" --download --seconds 240
```

The script downloads the two official CLI binaries, verifies their SHA-256 hashes, and uses fresh profiles and a loopback server. It does not connect to a personal browser.

[Script](reproduce.py) · [Recorded results](resultado-resumen.json) · [Full instructions and limits in Spanish](README-es.md)

## Sources and scope

[Upstream PR #1777](https://github.com/vercel-labs/agent-browser/pull/1777) · [Release 0.37.0](https://github.com/vercel-labs/agent-browser/releases/tag/v0.37.0)

This compares complete releases on Chromium 145.0.7632.6. It supports the observed difference for these two request fields in this local case. It does not isolate a single commit, establish when the bug first appeared, or validate production environments.
