# RP-001 Platform Adapter Models

## PlatformAdapter

- `platform`: stable platform id, e.g. `douyin`, `xiaohongshu`, `kuaishou`, `channels`, `wechat_mp`.
- `display_name`: user-visible Chinese platform name.
- `capabilities`: `PlatformCapabilities`.
- `adapter_version`: semantic adapter version.
- `runtime_modes`: `browser`, `api`, `sidecar`, `extension`, `official_api`.
- `health`: latest `AdapterHealth` summary.

## PlatformCapabilities

- `public_content_monitor`: can monitor public creator/account content.
- `keyword_search`: can discover content by keyword.
- `own_account_works`: can sync logged-in account works.
- `content_download`: can download or persist media assets.
- `comment_read`: can read comments.
- `comment_write`: can publish comments or replies.
- `publish`: can publish content.
- `follow_graph`: can sync or mutate follow/fan relationships.
- `dm`: can sync or send direct messages.
- `creator_center`: has separate creator-center runtime or credential.
- `requires_logged_account_for_read`: read requires logged-in account.
- `supports_browser_runtime`: adapter can run through Playwright/browser extension.
- `supports_api_runtime`: adapter can run through HTTP/API client.
- `known_limits`: documented constraints, e.g. 视频号 only own-account data.

## PlatformAccount

- `id`: internal UUID.
- `tenant_id`: owner scope.
- `platform`: platform id.
- `display_name`: nickname.
- `avatar_url`: avatar.
- `platform_user_id`: stable platform user id when known.
- `platform_handle`: visible handle/red_id/douyin_id.
- `credential_ref`: encrypted read credential reference.
- `creator_credential_ref`: encrypted creator/publish credential reference.
- `runtime_profile_ref`: browser profile, extension session, sidecar account, or official API token runtime.
- `proxy_ref`: optional proxy reference.
- `timezone`: account timezone.
- `locale`: account locale.
- `fingerprint_seed_ref`: deterministic fingerprint seed reference, never returned raw to UI.
- `status`: `active | invalid | risk_limited | disabled`.
- `last_health_check_at`: last credential/profile verification time.
- `last_active_at`: last successful adapter use.
- `platform_extra`: JSON for platform-specific ids such as `sec_uid`, `xsec_token` metadata, finder IDs.

## TargetRef

- `platform`: platform id.
- `target_kind`: `creator | keyword | content | own_account`.
- `platform_target_id`: platform target id.
- `display_name`: target label.
- `avatar_url`: optional avatar.
- `required_tokens`: platform-specific tokens such as `xsec_token`; stored as extra, never business field.
- `source_url`: original user input if available.
- `platform_extra`: raw platform-specific reference data.

## ContentItem

- `id`: internal UUID.
- `platform`: platform id.
- `platform_content_id`: platform content id.
- `owner_platform_user_id`: content owner platform user id.
- `source_target_id`: monitored target or own account source.
- `content_type`: `video | image_set | article | live | unknown`.
- `title`: title when platform has one.
- `description`: body/description.
- `cover_url`: cover.
- `published_at`: platform publish time.
- `metrics`: normalized metrics object.
- `media_assets`: list of `MediaAsset`.
- `raw_snapshot_ref`: object-store reference for raw platform response.
- `platform_extra`: platform-specific tokens and fields.

## ContentMetrics

- `views`: view/play count.
- `likes`: like count.
- `comments`: comment count.
- `shares`: share count.
- `collects`: collect/favorite count.
- `danmaku`: platform-specific bullet comments, when available.
- `followers`: account-level follower count when snapshotting account metrics.
- `extra`: platform-specific numeric metrics.

## MediaAsset

- `id`: internal UUID.
- `content_id`: owning content item.
- `kind`: `video | image | cover | audio | subtitle`.
- `url`: remote URL, may expire.
- `local_path`: local path for self-hosted/local mode only.
- `object_key`: object storage key for production.
- `mime`: mime type.
- `ext`: extension.
- `width`, `height`, `duration_ms`.
- `quality_label`: `highest | 1080 | 720 | original | unknown`.
- `checksum`: optional integrity checksum.
- `download_status`: `pending | downloading | done | failed | skipped`.
- `expires_at`: remote URL expiry when known.
- `error`: latest download error.

## Comment

- `id`: internal UUID.
- `platform`: platform id.
- `platform_content_id`: content id on platform.
- `platform_comment_id`: comment id on platform.
- `parent_comment_id`: parent id for replies.
- `author_platform_user_id`: commenter id when available.
- `author_display_name`: commenter nickname.
- `text`: comment text.
- `like_count`: likes.
- `created_at_platform`: platform timestamp.
- `raw_snapshot_ref`: raw response reference.
- `platform_extra`: platform-specific fields.

## PublishTask

- `task_id`: internal task id.
- `platform`: target platform.
- `account_id`: publishing account.
- `idempotency_key`: business idempotency key.
- `payload`: normalized publish payload.
- `media_refs`: media object references.
- `visibility`: `public | friends | private | platform_default`.
- `scheduled_at`: publish time.
- `status`: `draft | pending | publishing | done | failed | canceled`.
- `approval_status`: `not_required | pending | approved | rejected`.
- `attempt_count`: retry count.
- `result_url`: platform result URL.
- `platform_content_id`: published content id.
- `last_error`: latest error.
- `audit_log_ref`: audit trace.

## SocialActionTask

- `task_id`: internal task id.
- `platform`: platform id.
- `account_id`: actor account.
- `action`: `post_comment | reply_comment | follow | unfollow | send_dm`.
- `target_user_ref`: target platform user.
- `target_content_ref`: target content.
- `payload`: text or action payload.
- `idempotency_key`: dedupe key.
- `rate_limit_policy_ref`: applied rate limit policy.
- `scheduled_at`: execution time.
- `status`: `draft | pending | doing | done | failed | canceled`.
- `approval_status`: `not_required | pending | approved | rejected`.
- `result`: platform result id or `ok`.
- `last_error`: latest error.
- `audit_log_ref`: audit trace.

## AdapterHealth

- `platform`: platform id.
- `status`: `healthy | degraded | down | unknown`.
- `credential_status`: `valid | invalid | unknown | not_required`.
- `runtime_status`: browser/API/sidecar health.
- `last_success_at`: latest successful operation.
- `last_failure_at`: latest failed operation.
- `last_error_code`: normalized error code.
- `last_error_message`: safe, non-secret error message.
- `adapter_version`: adapter version.
- `diagnostics_ref`: optional raw diagnostic artifact reference.
