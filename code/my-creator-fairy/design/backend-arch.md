# Creator OS — Backend Architecture

## Tech stack

| 层级 | 选型 | 说明 |
|------|------|------|
| API 网关 | Python + FastAPI | 统一入口，路由/鉴权/限流 |
| 爬虫服务 | Python + Scrapy / Playwright | 平台数据采集 |
| Agent 服务 | Python + LangGraph | AI 分析与决策 |
| 事件分发 | Go + NATS JetStream | 高并发事件分发 (P1 用 Redis Streams) |
| 发布服务 | Go | 多平台并发发布、重试 |
| 主库 | PostgreSQL 16 | 业务数据 |
| 时序库 | TimescaleDB | 指标趋势数据 |
| 向量库 | Qdrant | 内容 embedding 检索 |
| 缓存 | Redis 7 | 热数据/会话/队列(P1) |
| 对象存储 | MinIO / S3 | 素材文件 |
| 容器编排 | Docker Compose (dev) → K8s (prod) | 一致环境 |

### 语言分工原则

**Python 做**：爬虫 (生态强)、文本处理 (jieba/spaCy)、AI 调用 (LangChain/LangGraph)、API 网关 (FastAPI 异步足够)、数据分析

**Go 做**：事件总线消费分发 (goroutine 天然适合高并发 fan-out)、多平台发布 (并发调 N 个平台 API)、WebSocket 推送网关、定时调度器

分界线：**IO 密集 + 生态依赖 → Python，CPU/并发密集 + 低延迟 → Go**

---

## 服务拆分与项目结构

基础设计，仅供参考
```
creator-os-server/
│
├── gateway/                          # FastAPI API 网关
│   ├── app/
│   │   ├── main.py                   # FastAPI 入口
│   │   ├── config.py                 # 配置 (pydantic-settings)
│   │   ├── deps.py                   # 依赖注入 (db session / current user)
│   │   │
│   │   ├── api/
│   │   │   ├── __init__.py
│   │   │   ├── router.py             # 总路由
│   │   │   ├── v1/
│   │   │   │   ├── auth.py           # 登录/注册/JWT
│   │   │   │   ├── accounts.py       # 平台账号 CRUD
│   │   │   │   ├── metrics.py        # 数据指标查询
│   │   │   │   ├── content.py        # 内容管理
│   │   │   │   ├── agents.py         # Agent 调用 (触发 / 查询结果)
│   │   │   │   ├── workflows.py      # 工作流 CRUD + 执行
│   │   │   │   ├── publish.py        # 发布任务
│   │   │   │   ├── topics.py         # 选题
│   │   │   │   └── knowledge.py      # 知识库
│   │   │   └── ws.py                 # WebSocket 端点 (事件推送)
│   │   │
│   │   ├── middleware/
│   │   │   ├── auth.py               # JWT 验证
│   │   │   ├── rate_limit.py         # 限流
│   │   │   └── logging.py            # 请求日志
│   │   │
│   │   └── schemas/                  # Pydantic 请求/响应模型
│   │       ├── auth.py
│   │       ├── account.py
│   │       ├── metric.py
│   │       ├── content.py
│   │       ├── agent.py
│   │       ├── workflow.py
│   │       └── common.py             # 分页/排序/通用响应
│   │
│   ├── pyproject.toml
│   ├── Dockerfile
│   └── alembic/                      # 数据库迁移
│       ├── alembic.ini
│       ├── env.py
│       └── versions/
│
├── services/
│   │
│   ├── crawler/                      # 爬虫服务
│   │   ├── app/
│   │   │   ├── main.py               # 独立 FastAPI (内部调用) 或 CLI
│   │   │   ├── scheduler.py          # 定时调度 (APScheduler)
│   │   │   │
│   │   │   ├── adapters/             # 平台适配器
│   │   │   │   ├── base.py           # BaseAdapter 抽象类
│   │   │   │   ├── bilibili.py
│   │   │   │   ├── xiaohongshu.py
│   │   │   │   ├── douyin.py
│   │   │   │   ├── youtube.py
│   │   │   │   ├── twitter.py
│   │   │   │   ├── wechat_mp.py      # 公众号
│   │   │   │   ├── zhihu.py
│   │   │   │   └── weibo.py
│   │   │   │
│   │   │   ├── trend/                # 趋势数据源
│   │   │   │   ├── google_trends.py
│   │   │   │   ├── weibo_hot.py
│   │   │   │   └── rss.py
│   │   │   │
│   │   │   └── pipeline.py           # 数据清洗 → 标准化 → 入库/发事件
│   │   │
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   │
│   ├── agent/                        # AI Agent 服务
│   │   ├── app/
│   │   │   ├── main.py               # FastAPI (接收事件触发 / API 调用)
│   │   │   ├── config.py
│   │   │   │
│   │   │   ├── agents/               # 各 Agent 实现
│   │   │   │   ├── base.py           # BaseAgent
│   │   │   │   ├── review_agent.py         # 账号复盘
│   │   │   │   ├── trending_agent.py       # 爆款分析
│   │   │   │   ├── topic_agent.py          # 选题推荐
│   │   │   │   ├── benchmark_agent.py      # 对标账号
│   │   │   │   ├── hotspot_agent.py        # 热点追踪
│   │   │   │   ├── comment_agent.py        # 评论分析
│   │   │   │   ├── fan_agent.py            # 粉丝分析
│   │   │   │   ├── risk_agent.py           # 风险评估
│   │   │   │   ├── growth_agent.py         # 增长策略
│   │   │   │   └── planner_agent.py        # 内容规划
│   │   │   │
│   │   │   ├── graphs/               # LangGraph 工作流定义
│   │   │   │   ├── review_graph.py         # 复盘流程图
│   │   │   │   ├── topic_graph.py          # 选题流程图
│   │   │   │   └── multi_agent.py          # 多 Agent 协作图
│   │   │   │
│   │   │   ├── tools/                # Agent 可调用的工具
│   │   │   │   ├── db_query.py             # 查数据库
│   │   │   │   ├── vector_search.py        # 向量检索
│   │   │   │   ├── web_search.py           # 搜索引擎
│   │   │   │   └── calculator.py           # 数据计算
│   │   │   │
│   │   │   └── prompts/              # Prompt 模板
│   │   │       ├── review.py
│   │   │       ├── topic.py
│   │   │       └── analysis.py
│   │   │
│   │   ├── pyproject.toml
│   │   └── Dockerfile
│   │
│   ├── event-dispatcher/             # Go 事件分发服务
│   │   ├── cmd/
│   │   │   └── dispatcher/
│   │   │       └── main.go
│   │   ├── internal/
│   │   │   ├── consumer/             # 事件消费者
│   │   │   │   ├── consumer.go
│   │   │   │   ├── metric_consumer.go
│   │   │   │   ├── comment_consumer.go
│   │   │   │   └── fan_consumer.go
│   │   │   ├── producer/             # 事件生产者
│   │   │   │   └── producer.go
│   │   │   ├── handler/              # 事件处理
│   │   │   │   └── handler.go
│   │   │   └── ws/                   # WebSocket 推送
│   │   │       ├── hub.go
│   │   │       └── client.go
│   │   ├── go.mod
│   │   ├── go.sum
│   │   └── Dockerfile
│   │
│   └── publisher/                    # Go 发布服务
│       ├── cmd/
│       │   └── publisher/
│       │       └── main.go
│       ├── internal/
│       │   ├── adapters/             # 各平台发布适配
│       │   │   ├── adapter.go        # 接口定义
│       │   │   ├── bilibili.go
│       │   │   ├── xiaohongshu.go
│       │   │   ├── douyin.go
│       │   │   ├── youtube.go
│       │   │   ├── twitter.go
│       │   │   ├── wechat_mp.go
│       │   │   └── zhihu.go
│       │   ├── scheduler/            # 定时发布
│       │   │   └── scheduler.go
│       │   ├── retry/                # 重试策略
│       │   │   └── retry.go
│       │   └── converter/            # 内容格式转换
│       │       ├── markdown.go
│       │       ├── html.go
│       │       └── media.go
│       ├── go.mod
│       ├── go.sum
│       └── Dockerfile
│
├── shared/                           # 跨服务共享 (Python)
│   ├── models/                       # SQLAlchemy ORM 模型
│   │   ├── __init__.py
│   │   ├── base.py                   # Base + mixins (id/timestamps)
│   │   ├── user.py
│   │   ├── platform_account.py
│   │   ├── content.py
│   │   ├── metric.py                 # 统一指标模型
│   │   ├── engagement.py
│   │   ├── comment.py
│   │   ├── fan.py
│   │   ├── topic.py
│   │   ├── workflow.py
│   │   └── publish_task.py
│   │
│   ├── events/                       # 事件 schema 定义
│   │   ├── __init__.py
│   │   ├── base.py                   # BaseEvent
│   │   ├── publish_event.py
│   │   ├── metric_event.py
│   │   ├── comment_event.py
│   │   ├── fan_event.py
│   │   └── trend_event.py
│   │
│   ├── db.py                         # 数据库连接 (async SQLAlchemy)
│   ├── redis.py                      # Redis 连接
│   ├── nats.py                       # NATS 连接
│   └── utils/
│       ├── datetime.py
│       └── crypto.py
│
├── proto/                            # Go/Python 共享的事件 schema
│   └── events/                       # Protocol Buffers 或 JSON Schema
│       ├── metric.proto
│       ├── publish.proto
│       └── common.proto
│
├── deploy/
│   ├── docker-compose.yml            # 本地开发全家桶
│   ├── docker-compose.prod.yml
│   ├── nginx/
│   │   └── nginx.conf
│   └── scripts/
│       ├── init-db.sh
│       └── seed-data.sh
│
├── Makefile                          # 统一命令入口
└── README.md
```

---

## 数据库设计

### PostgreSQL 核心表

```sql
-- 用户
CREATE TABLE users (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email       VARCHAR(255) UNIQUE NOT NULL,
    password    VARCHAR(255) NOT NULL,
    nickname    VARCHAR(100),
    avatar_url  TEXT,
    created_at  TIMESTAMPTZ DEFAULT now(),
    updated_at  TIMESTAMPTZ DEFAULT now()
);

-- 平台账号 (一个用户绑定多个平台)
CREATE TABLE platform_accounts (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id) ON DELETE CASCADE,
    platform        VARCHAR(50) NOT NULL,   -- bilibili / xiaohongshu / douyin ...
    platform_uid    VARCHAR(255) NOT NULL,   -- 平台侧用户ID
    display_name    VARCHAR(255),
    avatar_url      TEXT,
    credentials     JSONB,                   -- 加密存储的 token/cookie
    status          VARCHAR(20) DEFAULT 'active',  -- active / expired / disabled
    last_synced_at  TIMESTAMPTZ,
    created_at      TIMESTAMPTZ DEFAULT now(),
    UNIQUE(user_id, platform, platform_uid)
);

-- 内容 (统一模型，所有平台)
CREATE TABLE contents (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    account_id      UUID REFERENCES platform_accounts(id),
    platform        VARCHAR(50) NOT NULL,
    platform_cid    VARCHAR(255),            -- 平台侧内容ID
    content_type    VARCHAR(20) NOT NULL,     -- video / article / note / tweet
    title           TEXT,
    description     TEXT,
    cover_url       TEXT,
    tags            TEXT[],
    published_at    TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'draft',
    extra           JSONB DEFAULT '{}',       -- 平台特有字段
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);
CREATE INDEX idx_contents_account ON contents(account_id);
CREATE INDEX idx_contents_platform ON contents(platform, published_at DESC);

-- 选题
CREATE TABLE topics (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    title           TEXT NOT NULL,
    description     TEXT,
    source          VARCHAR(50),              -- agent / manual / hotspot
    source_ref      JSONB,                    -- 来源 Agent 的分析引用
    status          VARCHAR(20) DEFAULT 'idea', -- idea / planned / in_progress / done / archived
    priority        INT DEFAULT 0,
    target_platforms TEXT[],
    planned_date    DATE,
    tags            TEXT[],
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 发布任务
CREATE TABLE publish_tasks (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    content_id      UUID REFERENCES contents(id),
    account_id      UUID REFERENCES platform_accounts(id),
    platform        VARCHAR(50) NOT NULL,
    scheduled_at    TIMESTAMPTZ,
    status          VARCHAR(20) DEFAULT 'pending',  -- pending / publishing / success / failed / retry
    retry_count     INT DEFAULT 0,
    result          JSONB,                    -- 平台返回结果 (URL / ID / 错误)
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 工作流定义
CREATE TABLE workflows (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    name            VARCHAR(255) NOT NULL,
    description     TEXT,
    graph           JSONB NOT NULL,           -- ReactFlow 导出的 { nodes, edges }
    status          VARCHAR(20) DEFAULT 'draft',
    created_at      TIMESTAMPTZ DEFAULT now(),
    updated_at      TIMESTAMPTZ DEFAULT now()
);

-- 知识库
CREATE TABLE knowledge_entries (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID REFERENCES users(id),
    title           TEXT NOT NULL,
    content         TEXT,
    source_type     VARCHAR(50),              -- note / url / file / agent
    source_url      TEXT,
    tags            TEXT[],
    created_at      TIMESTAMPTZ DEFAULT now()
);
```

### TimescaleDB 时序表

```sql
-- 指标时序 (hypertable)
CREATE TABLE content_metrics (
    time            TIMESTAMPTZ NOT NULL,
    content_id      UUID NOT NULL,
    platform        VARCHAR(50) NOT NULL,
    views           BIGINT DEFAULT 0,
    likes           BIGINT DEFAULT 0,
    comments        BIGINT DEFAULT 0,
    shares          BIGINT DEFAULT 0,
    favorites       BIGINT DEFAULT 0,
    coins           BIGINT DEFAULT 0,         -- B站三连-投币
    danmaku         BIGINT DEFAULT 0,         -- B站弹幕
    extra           JSONB DEFAULT '{}'         -- 平台特有指标
);

SELECT create_hypertable('content_metrics', 'time');

CREATE INDEX idx_metrics_content ON content_metrics(content_id, time DESC);

-- 粉丝增长时序
CREATE TABLE fan_metrics (
    time            TIMESTAMPTZ NOT NULL,
    account_id      UUID NOT NULL,
    platform        VARCHAR(50) NOT NULL,
    followers       BIGINT DEFAULT 0,
    new_followers   BIGINT DEFAULT 0,
    unfollowers     BIGINT DEFAULT 0
);

SELECT create_hypertable('fan_metrics', 'time');

-- 常用聚合视图：日/周/月维度
CREATE MATERIALIZED VIEW content_metrics_daily
WITH (timescaledb.continuous) AS
SELECT
    time_bucket('1 day', time) AS day,
    content_id,
    platform,
    MAX(views) - MIN(views) AS views_delta,
    MAX(likes) - MIN(likes) AS likes_delta,
    MAX(comments) - MIN(comments) AS comments_delta,
    last(views, time) AS views_total,
    last(likes, time) AS likes_total
FROM content_metrics
GROUP BY day, content_id, platform;
```

---

## 统一数据模型 (Python)

```python
# shared/models/metric.py

from sqlalchemy import Column, String, BigInteger, JSON
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
from .base import Base

class ContentMetric(Base):
    """统一指标模型 — 所有平台的数据都归一到这个结构"""

    __tablename__ = "content_metrics"

    time        = Column(TIMESTAMP(timezone=True), primary_key=True)
    content_id  = Column(UUID, primary_key=True)
    platform    = Column(String(50), primary_key=True)

    # 通用指标 (所有平台都有)
    views       = Column(BigInteger, default=0)
    likes       = Column(BigInteger, default=0)
    comments    = Column(BigInteger, default=0)
    shares      = Column(BigInteger, default=0)
    favorites   = Column(BigInteger, default=0)

    # 平台特有指标 (B站的投币/弹幕, 小红书的收藏, Twitter的转推...)
    # 不在 schema 中穷举, 全部放这里
    extra       = Column(JSON, default=dict)
```

```python
# shared/events/base.py

from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID, uuid4

class BaseEvent(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    source: str            # 产生事件的服务名
    user_id: UUID | None = None

class MetricEvent(BaseEvent):
    event_type: str = "metric.updated"
    source: str = "crawler"
    content_id: UUID
    platform: str
    metrics: dict          # { views: 1234, likes: 56, ... }

class PublishEvent(BaseEvent):
    event_type: str = "publish.completed"
    source: str = "publisher"
    task_id: UUID
    platform: str
    status: str            # success / failed
    result: dict | None = None

class AgentResultEvent(BaseEvent):
    event_type: str = "agent.result"
    source: str = "agent"
    agent_type: str        # review / topic / trending ...
    result: dict
```

---

## 爬虫 Adapter 接口

```python
# services/crawler/app/adapters/base.py

from abc import ABC, abstractmethod
from pydantic import BaseModel
from datetime import datetime

class CrawledContent(BaseModel):
    platform_cid: str
    content_type: str
    title: str | None = None
    description: str | None = None
    cover_url: str | None = None
    tags: list[str] = []
    published_at: datetime | None = None
    metrics: dict = {}       # { views: N, likes: N, ... }
    extra: dict = {}         # 平台特有字段原样保留

class BaseAdapter(ABC):
    """所有平台爬虫适配器的基类"""

    platform: str            # 'bilibili' / 'xiaohongshu' / ...

    @abstractmethod
    async def fetch_content_list(
        self, account_id: str, page: int = 1
    ) -> list[CrawledContent]:
        """拉取账号的内容列表"""
        ...

    @abstractmethod
    async def fetch_content_metrics(
        self, content_ids: list[str]
    ) -> dict[str, dict]:
        """批量拉取内容指标 { platform_cid: { views, likes, ... } }"""
        ...

    @abstractmethod
    async def fetch_comments(
        self, content_id: str, page: int = 1
    ) -> list[dict]:
        """拉取评论列表"""
        ...

    @abstractmethod
    async def fetch_fans_count(self, account_id: str) -> int:
        """拉取粉丝数"""
        ...
```

```python
# services/crawler/app/adapters/bilibili.py

from playwright.async_api import async_playwright
from .base import BaseAdapter, CrawledContent

class BilibiliAdapter(BaseAdapter):
    platform = "bilibili"

    async def fetch_content_list(self, account_id, page=1):
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            ctx = await browser.new_context()
            pg = await ctx.new_page()
            await pg.goto(f"https://space.bilibili.com/{account_id}/video")
            # ... 解析视频列表
            items = []
            for card in await pg.query_selector_all(".video-card"):
                items.append(CrawledContent(
                    platform_cid=await card.get_attribute("data-aid"),
                    content_type="video",
                    title=await card.inner_text(".title"),
                    # ...
                    extra={"coins": 0, "danmaku": 0}  # B站特有
                ))
            await browser.close()
            return items

    async def fetch_content_metrics(self, content_ids):
        # 调用 B站 API
        ...

    async def fetch_comments(self, content_id, page=1):
        ...

    async def fetch_fans_count(self, account_id):
        ...
```

---

## Agent 服务架构

```python
# services/agent/app/agents/base.py

from abc import ABC, abstractmethod
from pydantic import BaseModel

class AgentInput(BaseModel):
    user_id: str
    account_id: str | None = None
    platform: str | None = None
    params: dict = {}

class AgentOutput(BaseModel):
    agent_type: str
    status: str = "success"
    result: dict
    metadata: dict = {}

class BaseAgent(ABC):
    agent_type: str

    @abstractmethod
    async def run(self, input: AgentInput) -> AgentOutput:
        ...
```

```python
# services/agent/app/graphs/review_graph.py
# 账号复盘 Agent — LangGraph 实现

from langgraph.graph import StateGraph, END
from typing import TypedDict

class ReviewState(TypedDict):
    user_id: str
    account_id: str
    platform: str
    # 各阶段产出
    raw_metrics: dict | None
    trend_analysis: str | None
    content_ranking: list | None
    recommendations: list | None
    final_report: str | None

async def fetch_metrics(state: ReviewState) -> ReviewState:
    """从数据库拉取最近 N 天的指标"""
    # ... query TimescaleDB
    state["raw_metrics"] = metrics
    return state

async def analyze_trends(state: ReviewState) -> ReviewState:
    """LLM 分析趋势"""
    # ... call LLM with raw_metrics
    state["trend_analysis"] = analysis
    return state

async def rank_content(state: ReviewState) -> ReviewState:
    """按表现排序内容"""
    state["content_ranking"] = ranking
    return state

async def generate_recommendations(state: ReviewState) -> ReviewState:
    """生成优化建议"""
    state["recommendations"] = recs
    return state

async def compile_report(state: ReviewState) -> ReviewState:
    """汇总报告"""
    state["final_report"] = report
    return state

# 构建图
graph = StateGraph(ReviewState)
graph.add_node("fetch_metrics", fetch_metrics)
graph.add_node("analyze_trends", analyze_trends)
graph.add_node("rank_content", rank_content)
graph.add_node("generate_recommendations", generate_recommendations)
graph.add_node("compile_report", compile_report)

graph.set_entry_point("fetch_metrics")
graph.add_edge("fetch_metrics", "analyze_trends")
graph.add_edge("fetch_metrics", "rank_content")        # 并行
graph.add_edge("analyze_trends", "generate_recommendations")
graph.add_edge("rank_content", "generate_recommendations")
graph.add_edge("generate_recommendations", "compile_report")
graph.add_edge("compile_report", END)

review_app = graph.compile()
```

---

## Go 事件分发服务

```go
// services/event-dispatcher/internal/consumer/consumer.go

package consumer

import (
    "context"
    "encoding/json"
    "log/slog"

    "github.com/nats-io/nats.go/jetstream"
)

type Event struct {
    EventID   string          `json:"event_id"`
    EventType string          `json:"event_type"`
    Timestamp string          `json:"timestamp"`
    Source    string           `json:"source"`
    UserID   string           `json:"user_id"`
    Payload  json.RawMessage  `json:"payload"`
}

type Handler func(ctx context.Context, event Event) error

type Dispatcher struct {
    js       jetstream.JetStream
    handlers map[string][]Handler
}

func NewDispatcher(js jetstream.JetStream) *Dispatcher {
    return &Dispatcher{
        js:       js,
        handlers: make(map[string][]Handler),
    }
}

func (d *Dispatcher) Register(eventType string, handler Handler) {
    d.handlers[eventType] = append(d.handlers[eventType], handler)
}

func (d *Dispatcher) Start(ctx context.Context, stream string) error {
    cons, err := d.js.CreateOrUpdateConsumer(ctx, stream, jetstream.ConsumerConfig{
        Durable:   "event-dispatcher",
        AckPolicy: jetstream.AckExplicitPolicy,
    })
    if err != nil {
        return err
    }

    iter, err := cons.Messages()
    if err != nil {
        return err
    }

    go func() {
        for {
            msg, err := iter.Next()
            if err != nil {
                slog.Error("consumer error", "err", err)
                continue
            }

            var event Event
            if err := json.Unmarshal(msg.Data(), &event); err != nil {
                slog.Error("unmarshal error", "err", err)
                msg.Nak()
                continue
            }

            handlers, ok := d.handlers[event.EventType]
            if !ok {
                msg.Ack()
                continue
            }

            for _, h := range handlers {
                if err := h(ctx, event); err != nil {
                    slog.Error("handler error",
                        "event_type", event.EventType,
                        "err", err,
                    )
                }
            }
            msg.Ack()
        }
    }()

    return nil
}
```

```go
// services/event-dispatcher/internal/ws/hub.go — WebSocket 推送

package ws

import (
    "sync"

    "github.com/gorilla/websocket"
)

type Hub struct {
    mu      sync.RWMutex
    clients map[string]map[*websocket.Conn]bool // userID -> connections
}

func NewHub() *Hub {
    return &Hub{clients: make(map[string]map[*websocket.Conn]bool)}
}

func (h *Hub) Register(userID string, conn *websocket.Conn) {
    h.mu.Lock()
    defer h.mu.Unlock()
    if h.clients[userID] == nil {
        h.clients[userID] = make(map[*websocket.Conn]bool)
    }
    h.clients[userID][conn] = true
}

func (h *Hub) Unregister(userID string, conn *websocket.Conn) {
    h.mu.Lock()
    defer h.mu.Unlock()
    delete(h.clients[userID], conn)
}

func (h *Hub) Push(userID string, message []byte) {
    h.mu.RLock()
    defer h.mu.RUnlock()
    for conn := range h.clients[userID] {
        conn.WriteMessage(websocket.TextMessage, message)
    }
}
```

---

## Go 发布服务

```go
// services/publisher/internal/adapters/adapter.go

package adapters

import "context"

type PublishRequest struct {
    TaskID      string
    Platform    string
    AccountID   string
    Credentials map[string]string
    Content     PublishContent
}

type PublishContent struct {
    Title       string
    Body        string            // markdown / html
    MediaURLs   []string
    CoverURL    string
    Tags        []string
    Extra       map[string]any    // 平台特有参数
}

type PublishResult struct {
    Success     bool
    PlatformURL string            // 发布后的链接
    PlatformID  string            // 平台侧内容ID
    Error       string
}

type Adapter interface {
    Platform() string
    Publish(ctx context.Context, req PublishRequest) (PublishResult, error)
}

// 适配器注册表
var registry = map[string]Adapter{}

func Register(a Adapter) {
    registry[a.Platform()] = a
}

func Get(platform string) (Adapter, bool) {
    a, ok := registry[platform]
    return a, ok
}
```

---

## API 网关核心路由

```python
# gateway/app/api/v1/metrics.py

from fastapi import APIRouter, Depends, Query
from datetime import date
from uuid import UUID

from app.deps import get_current_user, get_db
from app.schemas.metric import MetricResponse, MetricTrend

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("/{account_id}/overview", response_model=MetricResponse)
async def get_overview(
    account_id: UUID,
    start: date = Query(...),
    end: date = Query(...),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """获取账号在指定时间段的指标概览"""
    ...

@router.get("/{account_id}/trend", response_model=list[MetricTrend])
async def get_trend(
    account_id: UUID,
    metric: str = Query("views"),   # views / likes / comments / ...
    granularity: str = Query("day"),  # day / week / month
    start: date = Query(...),
    end: date = Query(...),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """获取指标趋势 (时序数据)"""
    ...

@router.get("/{account_id}/top-content")
async def get_top_content(
    account_id: UUID,
    sort_by: str = Query("views"),
    limit: int = Query(20, le=100),
    user=Depends(get_current_user),
    db=Depends(get_db),
):
    """获取表现最好的内容排行"""
    ...
```

```python
# gateway/app/api/v1/agents.py

from fastapi import APIRouter, Depends, BackgroundTasks
from uuid import UUID

router = APIRouter(prefix="/agents", tags=["agents"])

@router.post("/{agent_type}/run")
async def trigger_agent(
    agent_type: str,
    request: AgentRunRequest,
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
):
    """触发 Agent 执行 (异步)"""
    task_id = create_agent_task(agent_type, user.id, request)
    # 发事件到 NATS, agent 服务消费执行
    await publish_event("agent.trigger", {
        "task_id": task_id,
        "agent_type": agent_type,
        "user_id": str(user.id),
        "params": request.params,
    })
    return {"task_id": task_id, "status": "queued"}

@router.get("/tasks/{task_id}")
async def get_agent_result(
    task_id: UUID,
    user=Depends(get_current_user),
):
    """查询 Agent 执行结果"""
    ...
```

---

## Docker Compose (开发环境)

```yaml
# deploy/docker-compose.yml

services:
  postgres:
    image: timescale/timescaledb:latest-pg16
    ports: ["5432:5432"]
    environment:
      POSTGRES_DB: creatoros
      POSTGRES_USER: creatoros
      POSTGRES_PASSWORD: dev_password
    volumes:
      - pgdata:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]

  nats:
    image: nats:2-alpine
    ports: ["4222:4222", "8222:8222"]
    command: ["--jetstream", "--store_dir", "/data"]
    volumes:
      - natsdata:/data

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["6333:6333"]
    volumes:
      - qdrantdata:/qdrant/storage

  minio:
    image: minio/minio:latest
    ports: ["9000:9000", "9001:9001"]
    command: server /data --console-address ":9001"
    environment:
      MINIO_ROOT_USER: creatoros
      MINIO_ROOT_PASSWORD: dev_password
    volumes:
      - miniodata:/data

  gateway:
    build: ../gateway
    ports: ["8000:8000"]
    depends_on: [postgres, redis, nats]
    environment:
      DATABASE_URL: postgresql+asyncpg://creatoros:dev_password@postgres:5432/creatoros
      REDIS_URL: redis://redis:6379
      NATS_URL: nats://nats:4222
    volumes:
      - ../gateway:/app
    command: uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

  crawler:
    build: ../services/crawler
    depends_on: [postgres, redis, nats]
    environment:
      DATABASE_URL: postgresql+asyncpg://creatoros:dev_password@postgres:5432/creatoros
      NATS_URL: nats://nats:4222

  agent:
    build: ../services/agent
    depends_on: [postgres, redis, nats, qdrant]
    environment:
      DATABASE_URL: postgresql+asyncpg://creatoros:dev_password@postgres:5432/creatoros
      NATS_URL: nats://nats:4222
      QDRANT_URL: http://qdrant:6333
      LLM_API_KEY: ${LLM_API_KEY}

  event-dispatcher:
    build: ../services/event-dispatcher
    depends_on: [nats, redis]
    environment:
      NATS_URL: nats://nats:4222

  publisher:
    build: ../services/publisher
    depends_on: [nats, postgres]
    environment:
      NATS_URL: nats://nats:4222
      DATABASE_URL: postgres://creatoros:dev_password@postgres:5432/creatoros

volumes:
  pgdata:
  natsdata:
  qdrantdata:
  miniodata:
```

---

## Makefile (统一命令)

```makefile
.PHONY: dev up down migrate seed test lint

# 启动基础设施
up:
	cd deploy && docker compose up -d postgres redis nats qdrant minio

# 启动所有服务
dev:
	cd deploy && docker compose up -d

# 停止
down:
	cd deploy && docker compose down

# 数据库迁移
migrate:
	cd gateway && alembic upgrade head

# 种子数据
seed:
	cd deploy && bash scripts/seed-data.sh

# 单独启动 gateway (本地开发)
gateway:
	cd gateway && uvicorn app.main:app --reload --port 8000

# 单独启动 agent
agent:
	cd services/agent && uvicorn app.main:app --reload --port 8001

# 测试
test:
	cd gateway && pytest
	cd services/agent && pytest
	cd services/crawler && pytest
	cd services/event-dispatcher && go test ./...
	cd services/publisher && go test ./...
```

---

## 服务间通信总结

```
前端 ──HTTP/WS──→ Gateway (FastAPI :8000)
                    │
                    ├──HTTP──→ Agent Service (:8001)      [触发分析]
                    ├──HTTP──→ Crawler Service (:8002)     [手动触发抓取]
                    └──NATS──→ Event Bus
                                │
                    ┌───────────┼───────────────┐
                    │           │               │
              Event Dispatcher  Agent(消费)   Publisher(消费)
              (Go, WebSocket推送)
                    │
                    └──WS──→ 前端 (实时通知)
```

关键原则：

- 前端只和 Gateway 通信，不直连其他服务
- 服务间通过 NATS 事件解耦，不直接 HTTP 调用 (除了 Gateway → Agent/Crawler 的同步查询)
- Go 服务订阅 NATS 事件做高并发处理，处理完把结果再发事件
- Gateway 的 WebSocket 端点由 Go event-dispatcher 代理推送，Gateway 只做 HTTP
