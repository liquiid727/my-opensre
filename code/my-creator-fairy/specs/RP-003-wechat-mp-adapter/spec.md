# RP-003 WeChat MP Adapter

## Meta

- Spec ID: `RP-003`
- Title: `RP-003 WeChat MP Adapter`
- Epic: `Creator OS / MVP01 Adapters`
- Status: `in_progress_contract_slice`
- Owner Agent: `implementation-agent`
- Depends On:
  - `RP-001`
- Conditional Dependency:
  - `RP-005` before publishing, server-side credential persistence, or non-official session mode is enabled
- Source Design:
  - `design/platform-adapter.md`
  - `design/opensource-reference.md`
  - `design/mvp01.md`

## Goal

以微信官方 API 为首选实现公众号账号校验、自有文章同步、账号数据分析和图文草稿/发布能力，并将所有平台差异封装在 `wechat_mp` adapter 内。未认证或个人主体账号只能进入受限模式，不允许服务端明文托管后台 Cookie。

## Design Decisions

| Decision | Choice | Rationale |
| --- | --- | --- |
| MVP01 priority | 自有账号数据分析优先，图文发布第二 | 先支撑 AI 复盘，同时减少写操作与审核风险 |
| Primary integration | 微信官方 API | 合规、稳定，认证账号可获得统计与素材/发布能力 |
| Public article channel | 可选 `we-mp-rss` sidecar | 只通过 HTTP/Webhook 消费，不复制第三方实现 |
| Personal/unverified account | `restricted` capability mode | 不承诺 datacube 或自动发布，不托管服务端 Cookie |
| Credential access | 仅通过 `CredentialRef` | Adapter 不读取数据库明文字段，写能力依赖 RP-005 |

## Out of Scope

- 绕过微信平台权限、审核或认证限制。
- 将 `wechat_articles_spider` 等禁商用代码复制进仓库。
- C 端普通用户 Cookie 的服务端托管。
- 公众号评论自动回复、客服消息和粉丝画像扩展。
- 在本 spec 内实现通用调度器或密钥管理系统。

## Deliverables

- `app/platform_adapter/adapters/wechat_mp.py`
- `app/platform_adapter/registry.py` 注册 `wechat_mp`
- 显式公众号能力矩阵与 `restricted | official` 运行模式
- 官方 access token 获取、缓存和失效重试边界
- 自有文章与 datacube 数据归一化
- 图文草稿/发布 facade，默认受 RP-005 与人工审批门禁保护
- 单元测试、契约测试和实现记录

## Domain

- `WechatMpAdapter`: 公众号连接器。
- `WechatMpAccountMode`: `official | restricted`。
- `WechatArticle`: 归一为 `ContentItem(content_type=article)`。
- `WechatAccountMetrics`: `read_count`, `share_count`, `favorite_count`, `new_user`, `cancel_user`。
- `WechatPublishDraft`: 图文草稿，不等同于已发布内容。

### Invariants

- `official` 模式必须拥有有效 `app_id` 与 `app_secret` 引用，不接受请求体明文凭据。
- `restricted` 模式不得声明 datacube 或自动发布能力。
- access token 不写日志、不进入 API 响应，只保存在受控短期缓存中。
- 发布必须包含幂等键、操作者、审批状态和审计引用。
- 平台权限不足必须返回显式错误，不得以空数据伪装成功。

## Application

1. 检查公众号账号模式和已授权能力。
2. 获取或刷新官方 access token。
3. 拉取自有文章/素材并归一为 `ContentItem`。
4. 按日拉取账号和图文 datacube 指标，保存原始快照引用。
5. 创建图文草稿；审批通过后创建发布任务。
6. 查询 adapter 健康状态，识别权限不足、token 失效和平台限流。

## Repository

```text
app/platform_adapter/
  adapters/wechat_mp.py
  registry.py
  runtime.py
app/services/
  wechat_mp_accounts.py
  wechat_mp_analytics.py
  publishing.py
tests/
  test_wechat_mp_adapter.py
```

Adapter 只依赖 `credential_store`, `token_cache`, `audit_logger`, `clock`, `http_client` 等运行时端口，不直接读取 FastAPI 全局状态或 ORM session。

## API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/platform-adapters/wechat_mp/accounts/check` | 校验账号模式、权限和凭据状态 |
| `POST` | `/api/platform-adapters/wechat_mp/contents/fetch` | 拉取自有文章/素材 |
| `GET` | `/api/platform-adapters/wechat_mp/accounts/{account_id}/analytics` | 查询日期范围内账号和图文指标 |
| `POST` | `/api/platform-adapters/wechat_mp/publish-tasks` | 创建受审批保护的图文发布任务 |
| `GET` | `/api/platform-adapters/wechat_mp/health` | 返回脱敏健康状态 |

### Error Semantics

- `WECHAT_MP_ACCOUNT_NOT_VERIFIED`
- `WECHAT_MP_PERMISSION_DENIED`
- `WECHAT_MP_TOKEN_INVALID`
- `WECHAT_MP_TOKEN_REFRESH_FAILED`
- `WECHAT_MP_API_RATE_LIMITED`
- `WECHAT_MP_DATE_RANGE_INVALID`
- `WECHAT_MP_ARTICLE_REJECTED`
- `WRITE_ACTION_REQUIRES_APPROVAL`
- `CREDENTIAL_REF_REQUIRED`

## Database Impact

RP-003 不保存明文凭据。实现阶段复用或新增：

- `platform_accounts`：记录 `platform=wechat_mp`, `account_mode`, `credential_ref`, `capabilities_snapshot`。
- `content_items`：保存文章统一模型。
- `account_metric_snapshots`：按 `account_id, metric_date, metric_type` 唯一。
- `raw_snapshots`：保存平台响应的对象存储引用和 adapter 版本。

凭据表、版本、轮换与审计表由 `RP-005` 提供。

## Security And Operations

- 官方 API secret 只通过 Credential Store 解析。
- token 缓存按账号隔离，失效后最多刷新一次再重试原请求。
- 日志只记录 `account_id`, request id, error code 和脱敏平台响应摘要。
- 日期范围默认 7 天，单次不超过平台允许窗口；大范围由调度器分片。
- 发布默认关闭，通过 feature flag 和人工审批逐账号开启。

## Test Plan

- official/restricted 能力矩阵测试。
- token 缓存、失效刷新和并发去重测试。
- 文章及 datacube 指标归一化测试。
- 权限不足、限流、无数据和部分数据错误语义测试。
- API 响应和日志不泄露 app secret/access token 测试。
- 发布幂等、审批和审计事件测试；在 RP-005 完成前保持 blocked。

## Definition of Done

- [x] `wechat_mp` 作为具体 adapter 注册。
- [x] official/restricted 能力矩阵可被 API 查询。
- [x] 自有文章与 datacube 数据归一化测试通过。
- [ ] token 缓存和单次刷新重试行为有并发测试。
- [ ] API、日志和测试快照不含 secret/token。
- [ ] 发布路径通过 RP-005 的凭据、审批和审计门禁。
- [ ] 实现、评审和测试证据按 `RP-003` 归档。

## Assumptions And Open Questions

- 当前按“账号数据分析优先、图文发布第二”实施；若产品优先级调整，需要拆分发布子规格。
- 尚未确认公众号主体及认证状态，因此真实官方 API 集成测试不能成为第一阶段 CI 硬依赖。
- 若只能使用个人主体账号，第一阶段交付应降级为公开文章导入和本地运行器，不启用服务端 Cookie 模式。
