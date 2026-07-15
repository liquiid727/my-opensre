# RP-003 WeChat MP Adapter — Implementation Note

## Meta

- Spec ID: `RP-003`
- Status: `in_progress_contract_slice`
- Source Spec: `specs/RP-003-wechat-mp-adapter/spec.md`
- Implementation: `liquiid727/creatorhub@37f5af1..6983464`
- Date: `2026-07-15`

## Implemented Scope

- Added `wechat_mp` platform ID and concrete adapter registration.
- Added restricted/official capability modes; publishing stays disabled by default.
- Added network-free account target resolution with credential-bearing URL rejection.
- Added article and datacube metric normalization, including multi-article identity.
- Added offline contract tests in `tests/test_wechat_mp_adapter.py`.

## Deferred Scope

- Official token client/cache, account check, live article/datacube fetch, API endpoints, and publishing.
- Any publish path remains blocked on the complete RP-005 vault/write gate.

## Evidence

- Review: `reviews/RP-003-wechat-mp-adapter/review-report.md`
- Test result: `tests/results/RP-003-wechat-mp-adapter-20260715.json`
