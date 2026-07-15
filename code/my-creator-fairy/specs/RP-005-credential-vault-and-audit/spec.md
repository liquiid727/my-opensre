# RP-005 Credential Vault and Audit

## Meta

- Spec ID: `RP-005`
- Title: `RP-005 Credential Vault and Audit`
- Epic: `Creator OS / Platform Foundation`
- Status: `in_progress_contract_slice`
- Owner Agent: `architecture-agent`
- Depends On:
  - `RP-001`
- Unblocks:
  - `RP-003` publish path
  - production account flows and all automated write operations
- Source Design:
  - `design/platform-adapter.md`
  - `design/opensource-reference.md`

## Goal

建立平台凭据引用、加密存储、版本轮换、最小权限访问、响应脱敏和不可抵赖审计边界，使 adapter 与业务服务只持有短生命周期的解密结果，不再直接依赖数据库明文 Cookie、token、proxy 密码或本地 profile 路径。

## Design Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| Encryption | envelope encryption with authenticated encryption | 支持主密钥轮换，避免自研加密算法 |
| Key source | pluggable `KeyProvider`; self-hosted local provider first | 本地可用，同时可迁移云 KMS/系统 keychain |
| Secret access | internal capability only, no reveal HTTP API | 降低越权与日志泄漏面 |
| Audit | append-only event model | 支持追责、发布审批和安全审查 |
| C-end Cookie | prohibited on server | 改用官方 API、浏览器扩展或本地运行器 |

## Out of Scope

- 自研密码算法或把主密钥写入数据库。
- 面向用户返回明文 secret 的管理 API。
- 绕过平台账号授权或审批流程。
- 第一阶段接入所有云厂商 KMS；只定义端口和本地自托管实现。
- 将浏览器 profile 目录整体上传到服务端。

## Deliverables

- `CredentialStore` 与 `KeyProvider` 端口。
- 凭据创建、读取、轮换、撤销和健康检查服务。
- 加密凭据、版本和审计事件持久化模型及迁移。
- API DTO 脱敏规则和统一安全错误码。
- 写任务的幂等、审批、限流与审计关联校验。
- 单元、迁移、安全、并发和故障恢复测试。

## Domain

### CredentialRef

- `credential_ref_id`
- `tenant_id` / `owner_id`
- `platform`
- `account_id`
- `kind`: `official_api | browser_state | creator_state | proxy | local_runtime`
- `status`: `active | rotating | revoked | invalid`
- `active_version`
- `fingerprint`
- `expires_at`, `last_checked_at`

### CredentialVersion

- `credential_ref_id`, `version`
- `encrypted_data_key`
- `ciphertext`, `nonce`, `auth_tag`
- `key_provider`, `key_id`, `algorithm`
- `created_at`, `rotated_from_version`

### AuditEvent

- `event_id`, `occurred_at`, `request_id`, `trace_id`
- `actor_type`, `actor_id`, `action`
- `resource_type`, `resource_id`, `account_id`, `platform`
- `result`, `error_code`, `approval_ref`, `idempotency_key`
- `metadata_redacted`, `previous_event_hash`, `event_hash`

### Invariants

- 数据库中不得出现可直接使用的明文凭据。
- 主密钥不得与密文存储在同一数据源。
- 解密仅允许在受权 application service 内进行，并限制对象生命周期。
- secret、Cookie、token、proxy 密码和绝对 profile 路径不得进入日志、异常、API 或审计 metadata。
- 撤销后的版本不可再次解密用于平台操作。
- 每个写操作必须关联审批、幂等键和审计事件。

## Application

1. 创建凭据引用并写入第一个加密版本。
2. 根据调用方 capability 在内存中短暂解析凭据。
3. 轮换数据密钥或凭据内容，原版本只保留审计用途。
4. 撤销凭据并使所有后续 adapter 调用失败。
5. 检查凭据有效期和平台健康状态，只返回脱敏结果。
6. 写操作执行前校验凭据、审批、限流和幂等记录；执行后追加审计事件。

## Repository

```text
app/security/
  credential_store.py
  key_provider.py
  redaction.py
  audit.py
app/services/
  credentials.py
  write_gate.py
app/models/
  credential.py
  audit_event.py
migrations/
tests/
  test_credential_store.py
  test_credential_redaction.py
  test_write_gate.py
```

Adapter 只能接收 `credential_ref` 或由 runtime 注入的短生命周期 credential value；禁止自行查询 ORM 凭据字段。

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/credential-refs` | 创建凭据引用；请求体 secret 仅用于本次加密 |
| `POST` | `/api/credential-refs/{id}/rotate` | 创建新版本并切换 active version |
| `POST` | `/api/credential-refs/{id}/revoke` | 撤销凭据 |
| `POST` | `/api/credential-refs/{id}/check` | 执行脱敏健康检查 |
| `GET` | `/api/credential-refs/{id}` | 返回 metadata，不返回 secret |
| `GET` | `/api/audit-events` | 按权限查询脱敏审计事件 |

不存在 `reveal`, `decrypt`, `export-cookie` 等外部 API。

### Error Semantics

- `CREDENTIAL_NOT_FOUND`
- `CREDENTIAL_ACCESS_DENIED`
- `CREDENTIAL_REVOKED`
- `CREDENTIAL_EXPIRED`
- `CREDENTIAL_DECRYPT_FAILED`
- `KEY_PROVIDER_UNAVAILABLE`
- `CREDENTIAL_ROTATION_CONFLICT`
- `SECRET_MATERIAL_REJECTED`
- `AUDIT_WRITE_FAILED`
- `WRITE_ACTION_REQUIRES_APPROVAL`
- `IDEMPOTENCY_KEY_REQUIRED`

## Database Impact

新增：

- `credential_refs`
- `credential_versions`
- `adapter_audit_events`
- `write_idempotency_records`
- `write_approvals`

关键索引：

- `credential_refs(account_id, platform, kind, status)`
- unique `credential_versions(credential_ref_id, version)`
- `adapter_audit_events(account_id, occurred_at desc)`
- unique `write_idempotency_records(account_id, operation, idempotency_key)`
- `write_approvals(status, expires_at)`

迁移必须先支持双读：现有明文字段继续可读但禁止新写；完成回填与验证后再清空旧字段。回滚不得恢复明文写入。

## Security And Failure Handling

- 使用经过审计的 authenticated-encryption 实现，不实现自定义加密原语。
- 本地主密钥来源必须在仓库外，文件模式要求严格权限；生产环境建议 KMS/keychain。
- 解密失败、KMS 不可用或审计写入失败时，写操作 fail closed。
- 读操作可根据风险等级降级，但不得绕过撤销状态。
- 错误信息只暴露稳定错误码和安全提示；底层异常进入脱敏结构化日志。
- 审计事件包含 hash chain，用于检测删除或篡改，不把它误当作完整合规归档系统。

## Performance And Concurrency

- 解密结果仅允许进程内短 TTL 缓存，并按 `credential_ref_id + version` 隔离。
- 同一凭据轮换使用乐观锁，避免 active version 丢失更新。
- 同一账号写任务使用账号级串行锁；幂等记录在调用 adapter 前落库。
- 审计事件与任务状态尽量同事务提交；外部审计 sink 通过 outbox 异步投递。

## Test Plan

- 加密往返、篡改检测、错误 key 和撤销测试。
- 主密钥/数据密钥轮换与并发冲突测试。
- 数据库、API、日志、异常和审计事件的 secret 扫描测试。
- 旧明文字段双读回填、重复执行和回滚安全测试。
- 写任务缺少审批/幂等键时 fail-closed 测试。
- key provider、数据库或审计 sink 故障测试。
- 同账号并发写和重复请求测试。

## Definition of Done

- [ ] 凭据只以加密版本存储，主密钥不进入数据库或仓库。
- [ ] API、日志、异常和审计记录通过 secret 泄漏测试。
- [ ] 创建、轮换、撤销和健康检查测试通过。
- [ ] 明文字段完成双读迁移和回填验证。
- [ ] 所有写操作强制审批、幂等、账号锁和审计引用。
- [ ] 审计写入失败时写操作 fail closed。
- [ ] RP-003 发布路径只接收 `CredentialRef`。
- [ ] 实现、评审、迁移和安全测试证据按 `RP-005` 归档。

## Assumptions And Open Questions

- 第一阶段目标是单机/自托管；生产 KMS 供应商后续通过 `KeyProvider` 选择，不影响领域契约。
- 当前 `creatorhub` 的 `storage_state` 明文字段属于迁移输入，不是最终模型。
- 需要在实现前确认部署进程是否允许访问系统 keychain；否则使用仓库外的受限主密钥文件。
