# Creator OS — 开源项目参考表

> 采集层 / 热点层 / 发布层拟基于 GitHub 开源项目做底座,本文档是候选项目的统一参考。
> 上游:`design/idea.md`(数据层平台清单)、`design/goal.md`、`design/mvp01.md`(MVP01 = 公众号 + 小红书 + AI复盘 + AI热点 + AI选题)。
> **所有 Star 数与维护状态为 2026-07-08 联网核实的快照**,接入前以仓库当前状态为准。

---

## 一、选型原则

按优先级排序:

1. **许可红线**:产品目标是"先自用 → 后续 C 端/B 端商业化"。`仅供学习/禁止商用` 类项目自用阶段可以用,但必须进入[商业化替换清单](#六许可与合规红线);GPL 类项目只以**独立进程(sidecar)+ API 调用**方式使用,代码不并入本仓库,避免传染闭源产品。
2. **维护活跃度**:平台风控/接口月月在变,爬虫类项目一旦停更基本等于失效。已归档项目一律不作为依赖。
3. **接入方式**:优先"官方 API > 独立部署的开源服务 > 引为代码依赖 > 仅借鉴思路自写",隔离层永远是我们自己的 `BaseAdapter`(见 `design/backend-arch.md`),开源项目只在 Adapter 内部被调用,随时可替换。

---

## 二、平台数据获取策略矩阵

对齐 `idea.md` 数据层清单。优先级:P0 = MVP01,P1 = 下一阶段,P2 = 远期。

| 平台 | 优先级 | 官方接口 | 推荐开源方案 | 兜底方案 | 封禁风险 |
|------|--------|----------|--------------|----------|----------|
| 小红书 | **P0** | 无个人创作者开放 API | 自有数据:Spider_XHS / xhs(创作者平台接口);对标爆款:MediaCrawler | 创作者中心手动导出 | 高(风控极强,控制频率) |
| 公众号 | **P0** | 认证号有 datacube 数据接口;个人订阅号不可认证 | 内容通道:we-mp-rss;自有阅读/点赞数据:借鉴 wechat_articles_spider 的 mp 后台接口思路 | 公众号后台手动导出 Excel | 中 |
| 热点聚合(微博热搜等) | **P0** | — | newsnow / DailyHotApi / TrendRadar | 直接爬各热榜页 | 低(公开页面) |
| 抖音 | P1 | 开放平台门槛高(企业) | TikTokDownloader / MediaCrawler | 创作者中心手动导出 | 高 |
| B站 | P1 | 创作中心较开放 | bilibili-api | — | 低-中 |
| 知乎 | P1 | 无 | MediaCrawler | — | 中 |
| 微博(账号数据) | P1 | 无 | weibo-crawler;热搜已被热点聚合类覆盖 | — | 中 |
| RSS 源 | P1 | — | RSSHub | — | 低 |
| YouTube | P2 | **官方 Data API v3,免费合规** | 无需爬虫 | — | 低 |
| 视频号 | P2 | 生态封闭 | 数据侧无成熟开源方案;发布侧 social-auto-upload 支持 | 手动 | 高 |
| Twitter/X | P2 | 官方 API(付费) | — | — | 中 |
| Google Trends | P2 | 无官方 API | ~~pytrends~~ **已归档(2025-04),不可依赖**,届时评估 trendspy 等替代 | — | — |

---

## 三、候选项目分组表

### A. 小红书采集(P0)

| 项目 | Star | 许可 / 商用 | 维护(核实于 2026-07) | 功能覆盖 | 接入建议 |
|------|------|-------------|------------------------|----------|----------|
| [NanmiCoder/MediaCrawler](https://github.com/NanmiCoder/MediaCrawler) | 40k+ | MIT,但 README **明确禁止商用** | 活跃(789 commits) | 小红书/抖音/快手/B站/微博/贴吧/知乎 7 平台;关键词搜索、笔记、二级评论;Playwright 登录态方案,无需 JS 逆向 | **对标/爆款分析主力**。独立进程跑,产物入库;商业化前替换(作者有付费 Pro 版可作授权路径) |
| [cv-cat/Spider_XHS](https://github.com/cv-cat/Spider_XHS) | 6.7k | MIT,但 README **禁止任何商业化** | 活跃(v4.0.0,2026-04) | PC 端采集(用户/笔记/搜索/评论)+ **创作者平台**(上传图集/视频、蒲公英 KOL 数据);扫码/短信/cookie 三种登录、多账号 | **自有账号数据主力**(自用阶段)。JS 逆向签名,封装进 `adapters/xiaohongshu.py` 内部调用 |
| [ReaJason/xhs](https://github.com/ReaJason/xhs) | 2.2k | MIT(无禁商声明) | 一般(有停滞迹象,接入前验证 sign 可用性) | Web 端 + creator.xiaohongshu.com 请求封装,支持发布笔记;需自建 sign 服务 | 商业化阶段的**自研参考实现**(许可干净);现阶段做 Spider_XHS 的备选 |
| [lucasygu/redbook](https://github.com/lucasygu/redbook) | 未核实 | 未核实 | 较新项目 | 小红书 CLI,为 AI Agent 场景设计 | 观察项,接入前补充核实 |

### B. 公众号(P0)

| 项目 | Star | 许可 / 商用 | 维护(核实于 2026-07) | 功能覆盖 | 接入建议 |
|------|------|-------------|------------------------|----------|----------|
| [wechatpy](https://github.com/wechatpy/wechatpy) | 成熟项目 | MIT ✅ | 成熟稳定 | 微信官方 API 全家桶,含 datacube 数据统计接口 | **若注册认证主体公众号,首选官方路线**(合规、稳定、含图文分析数据) |
| [rachelos/we-mp-rss](https://github.com/rachelos/we-mp-rss) | 3.8k | MIT ✅ | **活跃**(v1.5.2,2026-04) | 公众号文章 → RSS/Markdown/PDF/DOCX/JSON,定时更新,**Webhook/API/AI Agent 接入**;FastAPI+Vue3,扫码授权 | **公众号内容通道首选**。Docker sidecar 部署,单体经 HTTP/Webhook 消费 |
| [cooderl/wewe-rss](https://github.com/cooderl/wewe-rss) | 9.6k | MIT | ⛔ **已归档(2026-05-11),只读** | 微信读书通道生成公众号 RSS;部分请求经第三方域名转发 | **不引入**(停止维护 + 第三方转发风险),仅作原理参考 |
| [wnma3mz/wechat_articles_spider](https://github.com/wnma3mz/wechat_articles_spider) | 3.5k | Apache-2.0,但 README **严禁商用** | ⚠️ 停滞(release 2021,README 更新 2023) | 文章 + **阅读数/点赞/评论**;依赖 mp 后台 cookie + 个人微信号 key | 不作代码依赖,**借鉴其 mp 后台接口文档自写 adapter**(个人订阅号拿自有数据的唯一主流思路) |
| [striver-ing/wechat-spider](https://github.com/striver-ing/wechat-spider) | 未核实 | 未核实 | 较旧 | 中间人抓包方案,阅读量/点赞/评论 | 备选思路参考,接入前补充核实 |

> 公众号尚未注册。注册时的关键决策:**企业/个体户主体可认证 → 走 wechatpy 官方数据接口(推荐);个人主体不可认证 → 只能走 mp 后台 cookie 采集**。

### C. 热点 / 趋势(P0,喂给 AI热点 + AI选题 Agent)

| 项目 | Star | 许可 / 商用 | 维护(核实于 2026-07) | 功能覆盖 | 接入建议 |
|------|------|-------------|------------------------|----------|----------|
| [ourongxing/newsnow](https://github.com/ourongxing/newsnow) | 20.9k | MIT ✅ | 活跃(v0.0.41,2026-06) | 中文实时热点聚合(微博/知乎/抖音/华尔街见闻等),**自带 MCP server**;Docker/Cloudflare 部署 | **热点主数据源**。sidecar 部署,Agent 经 API/MCP 消费(TrendRadar 也用它做数据源,质量经过大规模验证) |
| [imsyy/DailyHotApi](https://github.com/imsyy/DailyHotApi) | 3.9k | MIT ✅ | 维护中(v2.0.8,2025-08) | **50+ 热榜源**聚合,JSON + RSS 双格式;Docker/Vercel | 热点**备选/补充源**(源数量比 newsnow 多,更新频率略低) |
| [sansan0/TrendRadar](https://github.com/sansan0/TrendRadar) | **60.3k** | **GPL-3.0** ⚠️ | 非常活跃(v6.10.0,2026-06) | 11 平台热点 + **AI 筛选/翻译/分析简报** + MCP(21 个工具)+ 9 种推送渠道;Python + LiteLLM + SQLite | 与"AI热点 Agent"定位几乎重合。**GPL:代码不并入本仓库**,两种用法:① 独立部署当现成的热点简报服务先用起来;② 自写 Agent 时借鉴其筛选/简报的产品设计 |
| [DIYgod/RSSHub](https://github.com/DIYgod/RSSHub) | 30k+ | MIT ✅ | 活跃(社区巨大) | 万物皆可 RSS,覆盖 idea.md 数据层的 RSS 一环 | sidecar 部署,作为长尾信息源基础设施 |
| ~~[pytrends](https://github.com/GeneralMills/pytrends)~~ | 3.7k | — | ⛔ **已归档(2025-04-17)** | Google Trends 非官方接口 | **不引入**。P2 阶段再评估 trendspy 等替代品 |

### D. 抖音 / 其他平台(P1)

| 项目 | Star | 许可 / 商用 | 维护(核实于 2026-07) | 功能覆盖 | 接入建议 |
|------|------|-------------|------------------------|----------|----------|
| [JoeanAmier/TikTokDownloader](https://github.com/JoeanAmier/TikTokDownloader) | 15k | **GPL-3.0** ⚠️ | 活跃(v5.7+,文档 2026-04 更新) | 抖音账号作品/评论/搜索/**热榜**/数据统计,TikTok 侧同类 | 抖音采集主力候选。**独立进程 + API 方式使用**(自带 Web API 模式),隔离 GPL |
| [Evil0ctal/Douyin_TikTok_Download_API](https://github.com/Evil0ctal/Douyin_TikTok_Download_API) | 未逐一核实 | 以仓库为准 | — | 抖音/快手/TikTok/B站,异步高性能,开箱即用 API 服务 | 服务化形态天然适合 sidecar,P1 接入前核实 |
| [Nemo2011/bilibili-api](https://github.com/Nemo2011/bilibili-api) | 未逐一核实 | GPL-3.0(以仓库为准) | — | B站 API Python 封装(视频/评论/用户/直播) | P1 接入前核实;B站也可优先走创作中心官方数据 |
| [dataabc/weibo-crawler](https://github.com/dataabc/weibo-crawler) | 未逐一核实 | 学习用途(以仓库为准) | — | 微博用户/帖子采集 | 仅备选;热搜需求已被 C 组覆盖 |

### E. 多平台发布(P1,AI Production 层)

| 项目 | Star | 许可 / 商用 | 维护(核实于 2026-07) | 功能覆盖 | 接入建议 |
|------|------|-------------|------------------------|----------|----------|
| [dreammis/social-auto-upload](https://github.com/dreammis/social-auto-upload) | 13.1k | MIT ✅ **明确允许商用** | 活跃(2026-03 大重构中) | 抖音/B站/小红书/快手/视频号/百家/TikTok/YouTube;视频为主、抖音/小红书/快手支持图文;cookie + Playwright/Patchright,带 Web UI 和定时发布 | **服务端发布主力候选**,与 backend-arch 的 publisher 适配器设计同构,可直接借鉴其各平台实现 |
| [leaperone/MultiPost-Extension](https://github.com/leaperone/MultiPost-Extension) | 2.8k | Apache-2.0 ✅ | 活跃(v1.4.3,2026-06) | 浏览器扩展一键发布 10+ 平台(文/图/视频);**提供 Extension API + RESTful API 供外部程序调用** | **C 端阶段的关键路线**:凭据留在用户浏览器,规避服务端 cookie 托管的合规风险 |
| [wechatsync/Wechatsync](https://github.com/wechatsync/Wechatsync) | 5.9k | **GPL-3.0** ⚠️ | 活跃(v2.0.9,2026-03) | Chrome MV3 扩展,图文同步 **29+ 平台**(公众号/知乎/掘金/头条/B站专栏…),带 CLI 和 **MCP 协议**支持 | 图文分发候选。GPL:独立使用不并码;其 MCP 接口适合被我们的 Agent 直接调用 |

### F. Agent 编排

| 项目 | 说明 |
|------|------|
| [LangGraph](https://github.com/langchain-ai/langgraph) | **已选型**(见 `design/backend-arch.md`),MIT,复盘/热点/选题三个 Agent 进程内编排 |
| TrendRadar 的 MCP 工具集 | 设计参考:它把"热点查询/趋势追踪/情感分析/相似检索"拆成 21 个 MCP 工具给 LLM 调用,这个工具化粒度值得 AI热点/选题 Agent 借鉴 |

---

## 四、MVP01 推荐组合(精简单体口径)

MVP01 = 公众号 + 小红书 + AI复盘 + AI热点 + AI选题。单体架构下的落法:

```
FastAPI 单体
├── adapters/
│   ├── xiaohongshu.py   ← 内部调用 Spider_XHS(自有账号+创作者平台数据)
│   └── wechat_mp.py     ← 自写,借鉴 wechat_articles_spider 的 mp 后台接口思路
├── agents/(LangGraph 进程内)
│   ├── review_agent     ← 消费 adapters 入库的自有数据(AI复盘)
│   ├── hotspot_agent    ← 消费 newsnow sidecar 的 API/MCP(AI热点)
│   └── topic_agent      ← 热点 × 自有数据 × 对标数据 三路汇合(AI选题)
└── (PG16 + timescaledb + pgvector,单容器)

Docker sidecar(独立进程,随时可换)
├── newsnow          ← 热点主源(MIT)
├── we-mp-rss        ← 公众号内容通道(MIT)
└── MediaCrawler     ← 小红书对标/爆款采集,产物入库(禁商用→自用阶段)
```

三种接入模式的适用判断:

| 模式 | 适用 | 本期实例 |
|------|------|----------|
| pip 依赖引入 | MIT/Apache 且维护活跃 | wechatpy(若走认证号)、Spider_XHS(自用阶段) |
| **Docker sidecar + HTTP/MCP**(默认优先) | 服务化形态 / GPL 隔离 / 依赖复杂 | newsnow、we-mp-rss、MediaCrawler、TikTokDownloader(P1) |
| 仅借鉴思路自写 | 项目停滞 / 许可不允许 / 只需一小块 | wechat_articles_spider(停滞)、TrendRadar(GPL)、xhs(商业化阶段参考) |

---

## 五、与目标架构的关系

- 所有开源项目**只出现在 Adapter / sidecar 边界内**,统一数据模型(`contents` / `content_metrics`)不感知它们的存在——替换任何一个项目不影响 Agent 层。
- backend-arch 的爬虫服务(P1 拆分)届时直接继承这批 sidecar,不需要重新选型。

## 六、许可与合规红线

**商业化(C 端/B 端)前必须处理的替换清单:**

| 项目 | 问题 | 出路 |
|------|------|------|
| MediaCrawler | README 禁商用 | 购买作者 Pro 版授权,或自研替换 |
| Spider_XHS | README 禁商用 | 参考 xhs(MIT)自研创作者平台封装 |
| wechat_articles_spider | README 禁商用 + 停滞 | 本来就只借鉴思路,自写实现即无此问题 |
| TrendRadar / TikTokDownloader / Wechatsync / bilibili-api | GPL-3.0 | 保持独立进程 + API 调用即可继续用;绝不把代码拷入闭源仓库 |

**其他红线:**

1. **cookie/凭据托管**:自用阶段凭据留本机/自托管;C 端阶段必须转向浏览器扩展路线(MultiPost/Wechatsync 模式)或官方 API,**不做用户 cookie 的服务端托管**。
2. **采集范围**:只采自有账号数据 + 公开页面数据;对标账号只采公开内容;严格控制频率(每平台 QPS 上限 + 随机退避),遵守《个人信息保护法》与平台服务条款。
3. **已归档项目不引入**:wewe-rss、pytrends。
4. 表中"未核实"项在真正接入前必须补做与 P0 同等的核实(许可、维护、风控现状)。
