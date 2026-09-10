# Security and privacy

PACE is intended for one person on a trusted Windows computer. It listens on loopback, checks request Host/Origin values, and requires a local session cookie plus a CSRF token for changes. Static file access is restricted to the application assets. The interface escapes activity text, and configured race links must use HTTPS.

These controls do not protect against malware or someone using the same Windows account. The local journal is not encrypted by PACE. Do not expose the development server through a tunnel, on a LAN, or to the internet without designing authentication, authorization, TLS, and hardened hosting first.

## Garmin credentials

Passwords are not saved. Reusable Garmin sessions remain in memory and are written only when Windows DPAPI encryption succeeds. If encryption fails, PACE reports that sign-in will be needed after a restart; it does not save a plaintext session. Disconnect removes a persisted session without deleting runs.

The connector is pinned to garminconnect 0.3.5, which includes the token-file permissions fix for CVE-2026-54447. PACE uses its own encrypted persistence and does not call the connector's affected token-file writer. Dependency audits only cover known, reported issues and should be repeated when dependencies change.

## Before publishing source

The ignore file excludes the local data directory, databases and sidecars, session files, credentials, logs, virtual environments, activity exports, and backups. Never force-add these files. Renamed exports and screenshots can still disclose private data, so inspect the exact staged contents and run a secret scanner. Tests and examples must use synthetic data.

## Reporting a vulnerability

If GitHub private vulnerability reporting is enabled, use the repository's private reporting form. Otherwise, use a public issue only for a non-sensitive description and request a private channel before sharing exploit details. Never attach Garmin credentials, session files, or real activity exports to public reports.
