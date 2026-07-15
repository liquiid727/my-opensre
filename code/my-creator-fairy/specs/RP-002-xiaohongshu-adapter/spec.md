# RP-002 Xiaohongshu Adapter

## Meta

- Spec ID: `RP-002`
- Title: `RP-002 Xiaohongshu Adapter`
- Epic: `Creator OS / MVP01 Adapters`
- Status: `draft`
- Owner Agent: `implementation-agent`
- Depends On:
  - `RP-001`
- Source Design: `design/platform-adapter.md`
- Prototype Source: `/Users/mac_liquiid/Desktop/code/creatorhub/app/platforms/xhs/`

## Goal

把 `creatorhub` 小红书原型能力封装到 `PlatformAdapter` 契约后面，优先交付小红书能力矩阵、目标解析、笔记归一化、评论归一化和可继续接入真实 API 的 adapter facade。

## Why This Exists

MVP01 优先需要小红书账号数据、内容复盘和后续发布闭环。小红书也是当前原型里最能体现生产化复杂度的平台：读取态/创作态不同、关键词搜索可用、发布可走 API 直连和浏览器兜底、部分读接口依赖 `a1` 与 `xsec_token`。先封装小红书可以验证 RP-001 契约是否足以承载真实平台。

## Out of Scope

- 不改造 `engine/monitor.py` 全量扫描流程。
- 不实现凭据加密库或生产数据库迁移。
- 不把小红书 Cookie 暴露给 API。
- 不在本 spec 中实现公众号 adapter。
- 不保证真实网络抓取测试通过；真实调用依赖登录态和平台环境。

## Deliverables

- `creatorhub/app/platform_adapter/adapters/xiaohongshu.py`
- `creatorhub/app/platform_adapter/registry.py` 注册具体小红书 adapter。
- `creatorhub/tests/test_xiaohongshu_adapter.py`
- 小红书能力仍出现在 `/api/platform-adapters/capabilities`。
- `implementation/RP-002-xiaohongshu-adapter/implementation-note.md`

## Domain

- `XiaohongshuAdapter`: 具体小红书连接器 facade。
- `TargetRef`: 支持 `keyword`、`creator`、`content`。
- `ContentItem`: 从 `parse_note_detail` 输出的 Aweme-like 数据归一化。
- `Comment`: 从 `parse_comment / flatten_comments` 输出的 dict 归一化。

## Application

- `resolve_target(text, target_kind="keyword")` 本地返回关键词 TargetRef，不发网络请求。
- `resolve_target(text, target_kind="auto|note|creator")` 复用 `app.platforms.xhs.resolve`。
- `normalize_note_card(note_card, brief)` 复用 `parse_note_detail`，再归一成 `ContentItem`。
- `normalize_comments(raw_comments, platform_content_id)` 复用 `flatten_comments / parse_comment`，再归一成平台无关 comment dict。
- `fetch_creator_contents(...)` 和 `search_contents(...)` 作为真实 API 调用入口，但测试不依赖真实登录态。

## Repository

```text
app/platform_adapter/
  adapters/
    __init__.py
    xiaohongshu.py
  registry.py
  normalizers.py

tests/
  test_xiaohongshu_adapter.py
```

## API

RP-002 不新增外部 API；复用 RP-001 的能力矩阵接口。后续接真实服务时再把 `contents/fetch` 路由委托到 `default_registry.get("xhs")`。

## Database Impact

无数据库变更。

## Test Plan

- 小红书 adapter 是 `default_registry.get("xhs")` 返回的具体实现。
- 关键词 target 解析不依赖网络。
- note_card 能归一为 `ContentItem`，并保留 `xsec_token` 到 `platform_extra`。
- 评论树能拍平并归一为 `platform_comment_id / platform_content_id / parent_comment_id`。

## Definition of Done

- [ ] 小红书 adapter 已注册为具体 adapter。
- [ ] 小红书能力矩阵保持显式。
- [ ] 小红书关键词目标解析无需网络。
- [ ] 小红书笔记和评论归一化测试通过。
- [ ] 不引入新的真实平台请求作为测试前置条件。
