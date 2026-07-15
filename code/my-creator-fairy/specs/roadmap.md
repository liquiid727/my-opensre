# Spec Roadmap

Use this file as the only canonical index for epic grouping, release sequencing, and feature-spec dependencies.

## Creator OS

### Platform Foundation

- `RP-001 Platform Adapter Contract` _(implemented; production gates deferred to RP-004/RP-005)_

### MVP01 Adapters

- `RP-002 Xiaohongshu Adapter` _(implemented)_
- `RP-003 WeChat MP Adapter` _(contract slice implemented; official API integration planned)_
- `RP-004 Adapter Task Runtime` _(planned)_
- `RP-005 Credential Vault and Audit` _(metadata/redaction contract implemented; encrypted vault planned)_

## Release Order

### Release v0.1

1. `RP-001 Platform Adapter Contract`
2. `RP-002 Xiaohongshu Adapter`
3. `RP-003 WeChat MP Adapter`
4. `RP-004 Adapter Task Runtime`
5. `RP-005 Credential Vault and Audit`

## Dependency Notes

- `RP-002` depends on `RP-001`.
- `RP-003` depends on `RP-001`.
- `RP-004` depends on `RP-001` and provides scheduler/runtime support for `RP-002` and `RP-003`.
- `RP-005` depends on `RP-001` and must land before any C-end credential hosting or write-operation automation.
- `RP-003` read-only/official-API discovery may proceed after `RP-001`; publish and non-official credential modes require `RP-005` first.
