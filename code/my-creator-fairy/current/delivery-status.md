# Active Delivery Status

Updated: `2026-07-15`

## Completed Prototype Slices

- `RP-001`: platform adapter contracts, capability registry, normalized models, review and focused test evidence.
- `RP-002`: concrete Xiaohongshu adapter and XHS-first task-runtime delegation, review and focused test evidence.
- Implementation source: `liquiid727/creatorhub@1e969d5`.

## Active Implementation

- `RP-003`: concrete WeChat MP adapter, mode-aware capabilities, article/metrics normalization, and safe target resolution are implemented at `creatorhub@6983464`; live official API integration remains open.
- `RP-005`: credential metadata, audit contracts, recursive redaction, encoded-secret detection, and URL userinfo protection are implemented at `creatorhub@6983464`; encrypted persistence and rotation remain open.

## Gates

- RP-003 publishing and any non-official credential mode require RP-005.
- C-end service-side Cookie hosting is prohibited; use official API, browser extension, or local runtime.
- RP-004 still needs a formal spec before the current XHS runtime boundary can be promoted as a shared production scheduler.
