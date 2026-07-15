# Platform Adapter Design

## Meta

- Platform: `creator-os-platform-adapter`
- Status: `draft`
- Owner: `architecture-agent`
- Source Prototype: `/Users/mac_liquiid/Desktop/code/creatorhub`
- Source Spec: `specs/RP-001-platform-adapter-contract/spec.md`

## Purpose

把 `creatorhub` 作为多平台接入原型仓库，抽象为 Creator OS 生产平台可长期演进的 `platform-adapter` 能力层。该设计约束账号、内容、评论、发布、关注/私信、任务与能力声明的统一契约，让后续接入抖音、小红书、快手、视频号、公众号等平台时不再把平台分支散落到 API、调度器和 UI 中。

## Scope

本设计拥有以下稳定边界：

- 平台连接器注册表与能力矩阵。
- 账号身份、登录态、代理、浏览器 profile 与敏感凭据边界。
- 内容、媒体、指标、评论、发布、社交动作与任务状态的统一领域模型。
- 对 `creatorhub` 中平台函数、浏览器抓取、发布函数的封装迁移策略。
- 写操作的限流、幂等、审计、失败重试、人工确认和降级策略。

## Non-Goals

- 不直接承诺平台接口长期稳定；平台页面、选择器、Cookie 名称仍需健康检查和快速热修。
- 不在 C 端生产环境托管普通用户 Cookie；C 端阶段优先浏览器扩展、官方 API 或本地自托管连接器。
- 不把 GPL 或禁商用项目源码并入闭源主仓；只允许 sidecar/API/MCP 边界隔离。
- 不在 RP-001 中实现完整前端管理台、Agent 复盘或发布排期 UI。

## Architecture

```text
Creator OS Core
├── api / app services
│   ├── account service
│   ├── content service
│   ├── comment service
│   ├── publish service
│   └── task service
├── platform-adapter boundary
│   ├── registry.py
│   ├── contracts.py
│   ├── capabilities.py
│   ├── normalizers.py
│   └── adapters/
│       ├── douyin.py
│       ├── xiaohongshu.py
│       ├── kuaishou.py
│       ├── channels.py
│       └── wechat_mp.py
└── runtime infrastructure
    ├── browser runtime: Playwright profile / proxy / fingerprint
    ├── scheduler: scan / publish / comment / action queues
    ├── storage: Postgres + object storage + encrypted credential vault
    └── events: task status / metric updated / publish completed
```

`creatorhub` 当前可映射为：

- `app/platforms/*` → 平台原子能力，迁移为 adapter 内部实现。
- `app/browser/*` → browser runtime，作为连接器运行时依赖，不暴露给业务层。
- `app/engine/monitor.py` → 调度器原型，需要拆成任务编排 + adapter 调用。
- `app/models.py` → 统一领域模型原型，但需去抖音命名和 SQLite 耦合。
- `app/main.py` → API 原型，需要拆路由、服务、仓储和平台调用。

## Connector Contract

每个平台连接器必须实现显式能力声明，而不是靠 `if platform == ...` 隐式分支判断。

```python
from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol

class PlatformId(StrEnum):
    DOUYIN = "douyin"
    XIAOHONGSHU = "xiaohongshu"
    KUAISHOU = "kuaishou"
    CHANNELS = "channels"
    WECHAT_MP = "wechat_mp"

@dataclass(frozen=True)
class PlatformCapabilities:
    public_content_monitor: bool = False
    keyword_search: bool = False
    own_account_works: bool = False
    content_download: bool = False
    comment_read: bool = False
    comment_write: bool = False
    publish: bool = False
    follow_graph: bool = False
    dm: bool = False
    creator_center: bool = False
    requires_logged_account_for_read: bool = False
    supports_browser_runtime: bool = True
    supports_api_runtime: bool = False
    known_limits: list[str] = field(default_factory=list)

class PlatformAdapter(Protocol):
    platform: PlatformId
    capabilities: PlatformCapabilities

    async def login_start(self, request: LoginStartRequest) -> LoginStartResult: ...
    async def check_account(self, account: AccountIdentity) -> AccountHealth: ...
    async def resolve_target(self, target: TargetInput) -> TargetRef: ...
    async def fetch_contents(self, request: ContentFetchRequest) -> ContentFetchResult: ...
    async def fetch_comments(self, request: CommentFetchRequest) -> CommentFetchResult: ...
    async def publish(self, request: PublishRequest) -> PublishResult: ...
    async def post_comment(self, request: CommentWriteRequest) -> CommentWriteResult: ...
    async def fetch_account_assets(self, request: AccountAssetRequest) -> AccountAssetResult: ...
    async def execute_social_action(self, request: SocialActionRequest) -> SocialActionResult: ...
```

所有可选方法必须先由 `capabilities` 声明支持。业务层调用前检查能力；不支持时返回标准错误 `PLATFORM_CAPABILITY_UNSUPPORTED`，不得让空结果伪装成功。

## Unified Domain Model

### AccountIdentity

- `id`: 内部账号 ID。
- `platform`: 平台枚举。
- `display_name`, `avatar_url`, `platform_user_id`, `platform_handle`。
- `credential_ref`: 加密凭据引用，不直接存明文 Cookie。
- `creator_credential_ref`: 创作中心凭据引用。
- `runtime_profile_ref`: Playwright profile / browser extension session / official API token。
- `proxy_ref`, `timezone`, `locale`, `fingerprint_seed`。
- `status`: `active | invalid | risk_limited | disabled`。
- `last_health_check_at`, `last_active_at`。

`creatorhub.models.DouyinAccount` 应迁移为 `PlatformAccount`；`sec_uid`、`aweme_id` 这类平台字段只进入 `platform_extra` 或平台专用 ref。

### ContentItem

- `id`, `platform`, `platform_content_id`, `owner_account_ref`, `source_target_ref`。
- `content_type`: `video | image_set | article | live | unknown`。
- `title`, `description`, `cover_url`, `published_at`。
- `metrics`: `views`, `likes`, `comments`, `shares`, `collects`, `plays`。
- `media_assets`: 归一化媒体数组。
- `raw_snapshot_ref`: 原始响应快照引用。
- `platform_extra`: `xsec_token`、`sec_uid`、视频号助手字段等。

### MediaAsset

- `kind`: `video | image | cover | audio | subtitle`。
- `url`, `local_path`, `object_key`, `mime`, `ext`, `width`, `height`, `duration_ms`, `checksum`。
- `quality_label`, `download_status`, `expires_at`。

### Comment

- `platform_comment_id`, `platform_content_id`, `parent_comment_id`。
- `author_ref`, `author_display_name`, `text`, `like_count`, `created_at`。
- `raw_snapshot_ref`, `platform_extra`。

### PublishTask

- `task_id`, `platform`, `account_id`, `content_payload`, `media_refs`。
- `visibility`, `schedule_at`, `status`。
- `idempotency_key`, `attempt_count`, `last_error`, `result_url`, `platform_content_id`。
- 写操作必须保留 `operator`, `approval_status`, `audit_log_ref`。

### SocialActionTask

- `action`: `follow | unfollow | send_dm | post_comment | reply_comment`。
- `target_user_ref`, `target_content_ref`, `payload`。
- `status`, `scheduled_at`, `rate_limit_policy_ref`, `approval_status`, `audit_log_ref`。

## Capability Matrix From CreatorHub Prototype

| Platform | Public Monitor | Keyword Search | Own Works | Download | Comment Read | Comment Write | Publish | Follow/Fan | DM | Notes |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 抖音 | yes | no | yes | yes | yes | yes | yes | yes | yes | browser intercept + partial direct API |
| 小红书 | creator + keyword | yes | yes | yes | yes | yes | yes | partial | limited | 读取态 + 创作态，依赖 `a1` / `xsec_token` |
| 快手 | yes | no | yes | yes | yes | yes | yes | yes | partial | GraphQL/browser intercept |
| 视频号 | no | no | yes | limited | own only | own only | yes | no | no | 仅创作者助手，本账号数据；不可承诺下载搬运 |
| 公众号 | pending | pending | own/account data first | article/media only | comment depends on official account | pending | article publish pending | no | no | MVP01 需要新增连接器 |

## Data and Contracts

### Registry

- `register(adapter: PlatformAdapter)`：启动时注册。
- `get(platform: PlatformId)`：业务层唯一入口。
- `list_capabilities()`：前端与任务编排读取能力矩阵。
- `require_capability(platform, capability)`：统一抛出能力不支持错误。

### Runtime Context

连接器方法只接收 `AdapterRuntimeContext`，禁止直接读取全局配置或 FastAPI route 状态：

- `browser_runtime`
- `credential_store`
- `proxy_policy`
- `rate_limiter`
- `audit_logger`
- `object_store`
- `clock`
- `logger`

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

## Operational Constraints

- 所有写操作必须经过账号级串行锁、每日/每小时配额、最小间隔、活跃时段、幂等键和审计日志。
- 登录态、Cookie、proxy、profile 目录必须加密或引用化存储；API 响应只返回脱敏状态。
- 抓取任务必须保留原始快照和 adapter 版本，方便平台改版后回放诊断。
- 平台选择器和接口路径需要健康检查；失败时标记连接器 `degraded`，不要把异常吞成空列表。
- `creatorhub` 原型可以先作为本地 sidecar 或 subtree 参考，不直接混入主应用领域层。
- C 端生产阶段禁止服务端托管普通用户 Cookie；优先浏览器扩展、本地运行器或官方 API。

## Migration Plan

1. 在 Creator OS 中落 `platform_adapter/contracts.py` 和 `registry.py`，只定义契约和能力矩阵。
2. 把 `creatorhub.app.platforms.*.extract` 的 `Aweme / MediaItem` 归一为 `ContentItem / MediaAsset` normalizer。
3. 封装小红书为第一个 adapter，因为 MVP01 需要小红书账号数据和发布闭环。
4. 将 `creatorhub.app.engine.monitor` 拆成 `scan scheduler`、`publish scheduler`、`comment scheduler`、`social action scheduler`。
5. 将 `creatorhub.app.main` 中路由逻辑迁移到 service 层，API 只做 DTO 与权限校验。
6. 引入 credential vault、审计表、能力矩阵接口和连接器健康检查。

## Feature Spec Mapping

- `specs/RP-001-platform-adapter-contract/spec.md`：平台连接器契约与统一模型。
- 后续建议：
  - `RP-002-xiaohongshu-adapter`
  - `RP-003-wechat-mp-adapter`
  - `RP-004-adapter-task-runtime`
  - `RP-005-credential-vault-and-audit`

## Open Questions

- `creatorhub` 是作为 sidecar、subtree、还是只做参考代码迁移？当前建议先 sidecar/reference，等契约稳定后再选择性迁移。
- MVP01 的公众号能力优先级是“账号数据分析”还是“图文发布”？需要在 RP-003 前确认。
- 小红书生产化是否允许服务端持有自有账号 Cookie？自用阶段可行，C 端阶段需要扩展或本地运行器。
