# Security update 4.2

Release date: 2026-08-17

- The initial TAPADM password is generated randomly on each new installation.
  It is available once in `%LOCALAPPDATA%\TAP_Gestion_Loyers\TAP_PREMIER_MOT_DE_PASSE.txt`.
- Accounts and password hashes are stored locally and survive restarts.
- Password hashes use PBKDF2-HMAC-SHA256 (600,000 iterations).
- The mobile portal is bound to `127.0.0.1` by default. Set
  `mobile_portal.host` to `0.0.0.0` only to enable a trusted private Wi-Fi.
- A duplicate signature-payment implementation was removed from the public API.

