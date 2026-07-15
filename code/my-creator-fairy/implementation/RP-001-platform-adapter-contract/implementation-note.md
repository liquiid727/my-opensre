# RP-001 Platform Adapter Contract — Implementation Note

## Meta

- Spec ID: `RP-001`
- Source Spec: `specs/RP-001-platform-adapter-contract/spec.md`
- Source Design: `design/platform-adapter.md`
- Status: `implemented`
- Date: `2026-07-15`
- Owner Agent: `architecture-agent`

## Prototype Intake

`creatorhub` was cloned to `/Users/mac_liquiid/Desktop/code/creatorhub` and inspected as the platform-adapter prototype repository.

Key prototype facts:

- `app/platforms/` already groups platform-specific primitives by package: `douyin`, `xhs`, `kuaishou`, `channels`.
- Each platform exposes combinations of `resolve`, `extract`, `client`, and `publish`, but originally had no shared `PlatformAdapter` object or registry.
- `app/browser/` owns Playwright runtime, login flows, fetchers, account hub operations, identity/fingerprint, and profile/proxy isolation.
- `app/engine/monitor.py` is the main cross-platform orchestrator for scans, downloads, comments, publish tasks, comment rules, follow/unfollow, and DM actions.
- `app/main.py` mixes API routes, DB reads/writes, platform branching, validation, and orchestration.
- `app/models.py` holds the useful model inventory, but naming is prototype-biased: `DouyinAccount` carries all platforms; `aweme_id` is reused for note/photo/video ids; `sec_uid` is reused for other platform user ids.

## Implemented Scope

In `/Users/mac_liquiid/Desktop/code/creatorhub`:

- Added `app/platform_adapter/contracts.py` with platform IDs, capability declarations, normalized content/media/comment-adjacent models, target refs, and health records.
- Added `app/platform_adapter/capabilities.py` with explicit capability matrix for Douyin, XHS, Kuaishou, and Shipinhao.
- Added `app/platform_adapter/registry.py` with default registry and capability validation.
- Added `app/platform_adapter/normalizers.py` for legacy Aweme/comment normalization.
- Added `GET /api/platform-adapters/capabilities` and `POST /api/platform-adapters/{platform}/resolve-target` in `creatorhub/app/main.py`.
- Added `tests/test_platform_adapter_contract.py`.

## Current Platform Capability Observations

| Platform | Prototype Capability | Important Constraint |
| --- | --- | --- |
| 抖音 | login, public works, download, comments, publish, follow/fan, DM | keyword discovery not implemented; some direct APIs plus browser fallback |
| 小红书 | login, creator/keyword notes, download, comments, API/browser publish | requires `a1` and sometimes `xsec_token`; read and creator states differ |
| 快手 | login, public works, download, comments, publish, follow/fan partial | GraphQL/browser intercept; keyword discovery not implemented |
| 视频号 | login, own works/data/comments/publish | only creator-assistant own-account data; no public monitor; encrypted CDN makes download unreliable |

## Refactor Level Decision

- Level: `二级：模块重构`.
- Reason: platform-specific branches were already present in API, engine, browser, and models. Continuing with patches would make each new platform require unrelated edits in multiple locations.
- Current implementation keeps the legacy engine state machine intact while introducing an explicit adapter boundary and tests.

## Migration Strategy

1. Add contract-only `platform_adapter` module in the prototype codebase.
2. Add a fake adapter and capability matrix tests before moving real platform code.
3. Migrate normalizers first: `Aweme / MediaItem / parse_comment` → `ContentItem / MediaAsset / normalized comment dict`.
4. Wrap one platform first: 小红书, because MVP01 prioritizes 小红书 + 公众号 + AI复盘.
5. Move scheduler concerns out of adapter: retries, locks, rate limits, audit, and status transitions stay in services/schedulers.
6. Keep `creatorhub` as sidecar/reference until contracts stabilize; do not copy sensitive runtime assumptions directly into Creator OS business services.

## Validation

Executed in `/Users/mac_liquiid/Desktop/code/creatorhub`:

```bash
python3 -m compileall -q app/platform_adapter app/main.py app/engine/monitor.py tests
PYTHONPATH=. python3 tests/test_platform_adapter_contract.py
PYTHONPATH=. python3 tests/test_xiaohongshu_adapter.py
PYTHONPATH=. python3 tests/test_adapter_task_runtime.py
```

Result: all checks passed.

## Risks

- Platform pages and selectors are unstable; adapter health checks must catch drift.
- Cookie/storage_state/proxy/profile data are sensitive; production needs vaulting and response redaction.
- Write operations create account risk; rate limits and approval gates are not optional.
- 视频号 limitations must be represented in capabilities, otherwise UI will expose impossible monitor/download flows.
- License/commercial constraints from `design/opensource-reference.md` still apply when mixing third-party implementations.

## Delivery Chain

This note covers the transition from design/spec to implementation evidence for RP-001.

- Review: `reviews/RP-001-platform-adapter-contract/review-report.md`
- Test result: `tests/results/RP-001-platform-adapter-contract-20260715.json`
- Implementation commit: `liquiid727/creatorhub@1e969d5`
- Promotion: approved for the prototype slice; production write-task, health, and credential gates remain open.
