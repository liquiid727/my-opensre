# RP-001 Platform Adapter Contract

## Meta

- Spec ID: `RP-001`
- Title: `RP-001 Platform Adapter Contract`
- Epic: `Creator OS / Platform Foundation`
- Status: `draft`
- Owner Agent: `architecture-agent`
- Depends On: []
- Source Design: `design/platform-adapter.md`
- Prototype Source: `/Users/mac_liquiid/Desktop/code/creatorhub`
- Source Drafts:
  - `design/backend-arch.md`
  - `design/opensource-reference.md`
  - `design/mvp01.md`

## Goal

建立 Creator OS 的生产级平台连接器契约，把 `creatorhub` 的抖音 / 小红书 / 快手 / 视频号原型能力收敛为统一、可注册、可声明能力、可审计、可限流、可替换的 `platform-adapter` 边界。

## Why This Exists

`creatorhub` 已经验证了多平台接入的可行性：真实浏览器登录、接口响应拦截、发布、评论、本账号作品、关注/粉丝/私信、代理隔离等能力齐全。但当前实现的核心问题是平台分支散落在 `app/main.py`、`app/engine/monitor.py`、`app/browser/*` 中，且模型仍大量沿用抖音命名，如 `DouyinAccount`、`aweme_id`、`sec_uid`。如果直接在这个结构上叠生产业务，新增公众号、小红书账号复盘、发布排期、Agent 分析时会不断扩大耦合面。

本 spec 的目的不是重写所有平台实现，而是先确定生产平台的统一心智模型：业务层只依赖 `PlatformAdapter` 契约与统一领域模型；平台差异留在 adapter 内部；可用能力通过 capabilities 显式声明；写操作全部经过任务、限流、审计和人工确认边界。

## Out of Scope

- 不实现完整小红书、公众号、抖音、快手、视频号 adapter。
- 不实现 UI 管理台。
- 不迁移 `creatorhub` 全部路由和调度器。
- 不引入新的生产数据库迁移。
- 不承诺平台抓取/发布能力在目标平台改版后仍无需维护。
- 不在 C 端生产环境托管普通用户 Cookie。

## Deliverables

- `design/platform-adapter.md` 作为稳定设计文档。
- `specs/RP-001-platform-adapter-contract/model.md` 定义统一领域模型。
- `specs/RP-001-platform-adapter-contract/openapi.yaml` 定义能力矩阵和任务 API 草案。
- `implementation/RP-001-platform-adapter-contract/implementation-note.md` 记录从 `creatorhub` 盘点得到的迁移依据。
- `tests/plans/RP-001-platform-adapter-contract.test-plan.json` 定义契约验收测试计划。

## Domain

### Entities

- `PlatformAdapter`: 平台连接器，声明平台 ID、能力矩阵和统一方法。
- `PlatformCapabilities`: 能力矩阵，描述是否支持公开监控、关键词、发布、评论、私信等。
- `PlatformAccount`: 平台账号身份，不暴露明文凭据。
- `CredentialRef`: 指向加密凭据的引用。
- `RuntimeProfile`: 浏览器 profile、扩展 session、API token runtime 的抽象。
- `ContentItem`: 平台内容统一模型。
- `MediaAsset`: 视频、图片、封面、音频等媒体资产统一模型。
- `Comment`: 评论统一模型。
- `PublishTask`: 发布任务统一状态机。
- `SocialActionTask`: 评论、关注、取关、私信等写操作任务。
- `AdapterHealth`: 连接器健康状态。

### Invariants

- 平台能力必须显式声明；业务层不得通过 `if platform == ...` 推断能力。
- 不支持的能力必须返回标准错误，不得返回空列表伪装成功。
- 写操作必须有 `account_id`、幂等键、审计记录和限流策略。
- 凭据、Cookie、proxy、profile 路径不得在 API 响应中明文返回。
- 平台原始字段进入 `platform_extra` 或 `raw_snapshot_ref`，不得污染通用模型命名。
- Adapter 内部可以使用 Playwright、直连 API、sidecar 或浏览器扩展，但外部契约保持不变。

## Application

### Use Cases

1. 查询平台能力矩阵，用于前端决定哪些按钮可见、任务编排决定哪些能力可调用。
2. 创建/检查平台账号，返回脱敏账号状态和健康信息。
3. 解析平台目标链接，得到 `TargetRef`。
4. 拉取内容列表，归一为 `ContentItem`。
5. 拉取评论列表，归一为 `Comment`。
6. 创建发布任务，进入 `PublishTask` 状态机。
7. 创建评论/关注/私信任务，进入 `SocialActionTask` 状态机。
8. 查询 adapter 健康状态，发现选择器失效、登录态失效、代理异常或限流。

### Service Boundaries

- API 层只处理 DTO、鉴权、参数校验和错误映射。
- Application service 负责读取账号、任务、权限、限流和审计。
- Adapter registry 是平台能力唯一入口。
- Adapter 实现只处理平台差异，不直接控制业务任务状态。
- Scheduler 负责重试、并发、串行锁、夜间静默和状态推进。

## Repository

### Target Layout

```text
app/
  platform_adapter/
    contracts.py
    capabilities.py
    registry.py
    errors.py
    models.py
    normalizers.py
    runtime.py
    adapters/
      douyin.py
      xiaohongshu.py
      kuaishou.py
      channels.py
      wechat_mp.py
  services/
    accounts.py
    content.py
    comments.py
    publishing.py
    social_actions.py
    adapter_health.py
  schedulers/
    content_scan.py
    publish_queue.py
    comment_queue.py
    social_action_queue.py
```

### Prototype Mapping

| CreatorHub Path | Production Boundary |
| --- | --- |
| `app/platforms/*/resolve.py` | `PlatformAdapter.resolve_target` |
| `app/platforms/*/extract.py` | `normalizers.py` + adapter-private parser |
| `app/platforms/*/publish.py` | `PlatformAdapter.publish` |
| `app/platforms/xhs/client.py` | xiaohongshu adapter API runtime |
| `app/browser/manager.py` | `BrowserRuntime` |
| `app/browser/login.py` | `PlatformAdapter.login_start` implementation detail |
| `app/browser/*_fetcher.py` | adapter browser fetch implementation detail |
| `app/engine/monitor.py` | scheduler + application services |
| `app/models.py` | production domain models |
| `app/main.py` | API routers + service calls |

## API

See `openapi.yaml` for the draft API contract. Required endpoints:

- `GET /api/platform-adapters/capabilities`
- `GET /api/platform-adapters/{platform}/health`
- `POST /api/platform-adapters/{platform}/resolve-target`
- `POST /api/platform-adapters/{platform}/accounts/check`
- `POST /api/platform-adapters/{platform}/contents/fetch`
- `POST /api/platform-adapters/{platform}/comments/fetch`
- `POST /api/platform-adapters/{platform}/publish-tasks`
- `POST /api/platform-adapters/{platform}/social-action-tasks`

### Error Semantics

- `PLATFORM_CAPABILITY_UNSUPPORTED`
- `ACCOUNT_CREDENTIAL_INVALID`
- `ACCOUNT_PROXY_UNHEALTHY`
- `PLATFORM_RATE_LIMITED`
- `PLATFORM_SELECTOR_CHANGED`
- `PLATFORM_AUTH_REQUIRED`
- `PLATFORM_TARGET_NOT_FOUND`
- `MEDIA_URL_EXPIRED`
- `WRITE_ACTION_REQUIRES_APPROVAL`

## Database Impact

RP-001 只定义模型和契约，不执行数据库迁移。后续实现阶段建议新增：

- `platform_accounts`
- `credential_refs`
- `runtime_profiles`
- `content_items`
- `media_assets`
- `comments`
- `publish_tasks`
- `social_action_tasks`
- `adapter_health_checks`
- `adapter_audit_logs`

## Test Plan

- Contract unit tests: fake adapter 注册、能力查询、能力不支持错误。
- Normalizer tests: 将 `creatorhub` 的 `Aweme / MediaItem / Comment` 样例映射到统一模型。
- Scheduler tests: 写操作每日/每小时限流、账号串行锁、幂等键、状态转移。
- Security tests: API 响应不泄露 Cookie、proxy 密码、profile 路径。
- Capability matrix tests: 视频号不支持公开监控，小红书支持关键词，抖音/快手暂不支持关键词。
- Regression tests: 平台 selector/API 失败必须标记 degraded，不得吞成成功空结果。

## Definition of Done

- [ ] `PlatformAdapter` 契约和 capabilities 字段稳定。
- [ ] 统一模型不再出现抖音专用命名作为跨平台字段。
- [ ] 业务层调用平台能力必须通过 registry。
- [ ] 所有写操作任务都有幂等、限流、审计和人工确认扩展点。
- [ ] `creatorhub` 原型能力已映射到迁移清单。
- [ ] `openapi.yaml` 覆盖能力矩阵、健康检查和任务创建。
- [ ] 测试计划覆盖安全、限流、能力声明和降级语义。
- [ ] 后续小红书 adapter spec 可直接依赖本契约。
