# Creator OS — Frontend Architecture

## Tech stack

| 层级 | 选型 | 说明 |
|------|------|------|
| 桌面壳 | Tauri 2.0 | Rust 后端，系统 WebView 渲染 |
| 框架 | React 19 + TypeScript 5.x | 严格模式，全量 TS |
| 构建 | Vite 6 | 开发快、HMR 快、Tauri 官方推荐 |
| 状态管理 | Zustand + Immer | 轻量、不模板化、适合跨模块共享 |
| 路由 | React Router 7 (桌面/Web) | 文件式路由，lazy loading |
| 画布 | @xyflow/react (ReactFlow v12) | 节点编辑器，工作流可视化 |
| 样式 | Tailwind CSS 4 | 原子化 CSS，和 Tauri 配合好 |
| 组件库 | Radix UI (headless) + 自建 | 无样式约束，完全可控 |
| 图表 | Recharts / ECharts | 数据 Dashboard |
| 富文本 | Tiptap 2 | 脚本编辑器、知识库 |
| HTTP | ky / ofetch | 轻量，支持拦截器 |
| 国际化 | i18next | 预留中英文 |
| Monorepo | pnpm workspace + Turborepo | 多包管理、构建缓存 |

### 为什么选 Zustand 不选 Redux / Jotai

- Redux：Creator OS 不是超大团队协作项目，Redux 的 action/reducer/slice 模板代码太多，开发效率低
- Jotai：原子化状态适合碎片化场景，但工作流画布需要集中式 store（节点/边/执行状态是一个整体），Zustand 的 slice pattern 更匹配
- Zustand：体积 < 2KB，天然支持 React 外部订阅（Tauri IPC 回调可以直接写 store），和 ReactFlow 搭配有成熟实践

---

## Monorepo 项目结构

```
creator-os/
│
├── apps/
│   ├── desktop/                    # Tauri 桌面端入口
│   │   ├── src-tauri/
│   │   │   ├── src/
│   │   │   │   ├── main.rs         # Tauri 入口
│   │   │   │   ├── commands/       # Rust commands (invoke 调用)
│   │   │   │   │   ├── mod.rs
│   │   │   │   │   ├── file_ops.rs       # 文件操作(缩略图/素材)
│   │   │   │   │   ├── video.rs          # 视频处理
│   │   │   │   │   └── system.rs         # 系统信息
│   │   │   │   ├── plugins/        # Tauri 插件注册
│   │   │   │   └── lib.rs
│   │   │   ├── tauri.conf.json     # Tauri 配置
│   │   │   ├── capabilities/       # 权限声明
│   │   │   └── Cargo.toml
│   │   ├── index.html
│   │   └── package.json
│   │
│   └── web/                        # Web 端入口 (共享前端代码)
│       ├── vite.config.ts
│       ├── index.html
│       └── package.json
│
├── packages/
│   ├── app/                        # 主应用 (路由 + 页面组装)
│   │   ├── src/
│   │   │   ├── main.tsx            # React 挂载
│   │   │   ├── app.tsx             # 根组件 + Provider
│   │   │   ├── router.tsx          # 路由定义
│   │   │   │
│   │   │   ├── layouts/
│   │   │   │   ├── root-layout.tsx         # 顶层布局 (侧边栏 + 主区)
│   │   │   │   ├── dashboard-layout.tsx    # 数据面板布局
│   │   │   │   └── workspace-layout.tsx    # 创作工作台布局
│   │   │   │
│   │   │   └── pages/
│   │   │       ├── dashboard/
│   │   │       │   ├── overview.tsx        # 数据总览
│   │   │       │   ├── account-review.tsx  # 账号复盘
│   │   │       │   ├── content-analysis.tsx
│   │   │       │   └── fan-analysis.tsx
│   │   │       ├── workspace/
│   │   │       │   ├── topics.tsx          # 选题面板
│   │   │       │   ├── script-editor.tsx   # 脚本编辑
│   │   │       │   ├── media.tsx           # 素材管理
│   │   │       │   ├── publish.tsx         # 发布管理
│   │   │       │   └── schedule.tsx        # 排期日历
│   │   │       ├── canvas/
│   │   │       │   └── workflow.tsx        # 工作流画布入口
│   │   │       ├── knowledge/
│   │   │       │   └── index.tsx           # 知识库
│   │   │       └── settings/
│   │   │           ├── accounts.tsx        # 平台账号管理
│   │   │           └── preferences.tsx
│   │   └── package.json
│   │
│   ├── ui/                         # 基础 UI 组件库
│   │   ├── src/
│   │   │   ├── index.ts
│   │   │   ├── button.tsx
│   │   │   ├── input.tsx
│   │   │   ├── modal.tsx
│   │   │   ├── dropdown.tsx
│   │   │   ├── toast.tsx
│   │   │   ├── sidebar.tsx
│   │   │   ├── data-table.tsx
│   │   │   ├── card.tsx
│   │   │   ├── tabs.tsx
│   │   │   ├── calendar.tsx
│   │   │   └── chart-wrapper.tsx
│   │   └── package.json
│   │
│   ├── stores/                     # Zustand 状态管理
│   │   ├── src/
│   │   │   ├── index.ts
│   │   │   ├── use-auth-store.ts           # 用户认证
│   │   │   ├── use-account-store.ts        # 平台账号
│   │   │   ├── use-dashboard-store.ts      # 数据面板
│   │   │   ├── use-workspace-store.ts      # 工作台全局
│   │   │   ├── use-topic-store.ts          # 选题
│   │   │   ├── use-script-store.ts         # 脚本编辑
│   │   │   ├── use-publish-store.ts        # 发布状态
│   │   │   ├── use-canvas-store.ts         # 画布 (节点/边/执行)
│   │   │   └── use-notification-store.ts   # 通知/事件推送
│   │   └── package.json
│   │
│   ├── canvas/                     # ReactFlow 画布模块
│   │   ├── src/
│   │   │   ├── index.ts
│   │   │   ├── workflow-canvas.tsx         # 画布主组件
│   │   │   ├── nodes/                      # 自定义节点 (全部 React.memo)
│   │   │   │   ├── index.ts               # nodeTypes 注册
│   │   │   │   ├── base-node.tsx           # 节点基类
│   │   │   │   ├── agent-node.tsx          # Agent 节点
│   │   │   │   ├── data-source-node.tsx    # 数据源节点
│   │   │   │   ├── transform-node.tsx      # 数据变换节点
│   │   │   │   ├── output-node.tsx         # 输出节点
│   │   │   │   └── condition-node.tsx      # 条件分支节点
│   │   │   ├── edges/
│   │   │   │   ├── index.ts
│   │   │   │   └── animated-edge.tsx
│   │   │   ├── panels/
│   │   │   │   ├── node-palette.tsx        # 左侧节点面板 (拖入)
│   │   │   │   ├── node-inspector.tsx      # 右侧属性面板
│   │   │   │   └── execution-log.tsx       # 执行日志
│   │   │   └── hooks/
│   │   │       ├── use-canvas-actions.ts   # 画布操作
│   │   │       ├── use-drag-drop.ts        # 拖放
│   │   │       └── use-execution.ts        # 工作流执行
│   │   └── package.json
│   │
│   ├── editor/                     # 富文本编辑器模块
│   │   ├── src/
│   │   │   ├── index.ts
│   │   │   ├── script-editor.tsx          # 脚本编辑器
│   │   │   ├── extensions/                # Tiptap 扩展
│   │   │   │   ├── ai-complete.ts         # AI 补全
│   │   │   │   ├── mention.ts             # @提及
│   │   │   │   └── variable.ts            # 变量插入
│   │   │   └── toolbar.tsx
│   │   └── package.json
│   │
│   ├── api/                        # API 客户端
│   │   ├── src/
│   │   │   ├── index.ts
│   │   │   ├── client.ts                  # HTTP 客户端 (拦截器/错误处理)
│   │   │   ├── endpoints/
│   │   │   │   ├── auth.ts
│   │   │   │   ├── accounts.ts            # 平台账号
│   │   │   │   ├── metrics.ts             # 数据指标
│   │   │   │   ├── agents.ts              # Agent 调用
│   │   │   │   ├── content.ts             # 内容管理
│   │   │   │   ├── publish.ts             # 发布
│   │   │   │   └── workflow.ts            # 工作流
│   │   │   ├── types/                     # 请求/响应类型
│   │   │   │   ├── index.ts
│   │   │   │   ├── metric.types.ts
│   │   │   │   ├── content.types.ts
│   │   │   │   ├── agent.types.ts
│   │   │   │   └── workflow.types.ts
│   │   │   └── ws.ts                      # WebSocket 客户端 (事件推送)
│   │   └── package.json
│   │
│   └── platform/                   # 平台适配层
│       ├── src/
│       │   ├── index.ts
│       │   ├── tauri.ts                   # Tauri invoke 封装
│       │   ├── web.ts                     # Web fallback
│       │   └── capabilities.ts            # 能力检测
│       └── package.json
│
├── pnpm-workspace.yaml
├── turbo.json
├── tsconfig.base.json
├── tailwind.config.ts
├── .env.development
├── .env.production
└── README.md
```

---

## 状态管理架构

### Store 设计原则

1. **按领域拆分 store**，不做一个巨型 store
2. **画布 store 和 UI store 分离**——ReactFlow 的节点/边数据变更频繁，不能和 UI 状态混在一起
3. **Zustand 的 subscribeWithSelector** 做精确订阅，避免不相关的 re-render
4. **Immer middleware** 让深层嵌套更新保持不可变性又写起来简单

### 核心 Store 示例

```typescript
// use-canvas-store.ts — 工作流画布状态

import { create } from 'zustand'
import { immer } from 'zustand/middleware/immer'
import { subscribeWithSelector } from 'zustand/middleware'
import {
  type Node, type Edge,
  applyNodeChanges, applyEdgeChanges,
  type OnNodesChange, type OnEdgesChange, type OnConnect,
  addEdge,
} from '@xyflow/react'

type ExecutionState = 'idle' | 'running' | 'success' | 'error'

interface CanvasStore {
  // --- data ---
  nodes: Node[]
  edges: Edge[]
  selectedNodeId: string | null
  executionState: ExecutionState

  // --- actions ---
  onNodesChange: OnNodesChange
  onEdgesChange: OnEdgesChange
  onConnect: OnConnect
  addNode: (node: Node) => void
  removeNode: (id: string) => void
  selectNode: (id: string | null) => void
  updateNodeData: (id: string, data: Record<string, unknown>) => void
  setExecutionState: (state: ExecutionState) => void

  // --- serialization ---
  exportWorkflow: () => { nodes: Node[]; edges: Edge[] }
  importWorkflow: (data: { nodes: Node[]; edges: Edge[] }) => void
}

export const useCanvasStore = create<CanvasStore>()(
  subscribeWithSelector(
    immer((set, get) => ({
      nodes: [],
      edges: [],
      selectedNodeId: null,
      executionState: 'idle',

      onNodesChange: (changes) =>
        set((s) => { s.nodes = applyNodeChanges(changes, s.nodes) }),

      onEdgesChange: (changes) =>
        set((s) => { s.edges = applyEdgeChanges(changes, s.edges) }),

      onConnect: (connection) =>
        set((s) => { s.edges = addEdge(connection, s.edges) }),

      addNode: (node) =>
        set((s) => { s.nodes.push(node) }),

      removeNode: (id) =>
        set((s) => {
          s.nodes = s.nodes.filter((n) => n.id !== id)
          s.edges = s.edges.filter((e) => e.source !== id && e.target !== id)
        }),

      selectNode: (id) =>
        set((s) => { s.selectedNodeId = id }),

      updateNodeData: (id, data) =>
        set((s) => {
          const node = s.nodes.find((n) => n.id === id)
          if (node) node.data = { ...node.data, ...data }
        }),

      setExecutionState: (state) =>
        set((s) => { s.executionState = state }),

      exportWorkflow: () => {
        const { nodes, edges } = get()
        return { nodes, edges }
      },

      importWorkflow: ({ nodes, edges }) =>
        set((s) => { s.nodes = nodes; s.edges = edges }),
    }))
  )
)
```

```typescript
// use-dashboard-store.ts — 数据面板状态

import { create } from 'zustand'

interface DateRange {
  start: string
  end: string
}

interface DashboardStore {
  activePlatform: string           // 当前选中平台
  dateRange: DateRange             // 时间范围
  metricsLoading: boolean
  metrics: PlatformMetrics | null
  
  setPlatform: (platform: string) => void
  setDateRange: (range: DateRange) => void
  fetchMetrics: () => Promise<void>
}

export const useDashboardStore = create<DashboardStore>()((set, get) => ({
  activePlatform: 'bilibili',
  dateRange: { start: '', end: '' },
  metricsLoading: false,
  metrics: null,

  setPlatform: (platform) => {
    set({ activePlatform: platform })
    get().fetchMetrics()
  },

  setDateRange: (range) => {
    set({ dateRange: range })
    get().fetchMetrics()
  },

  fetchMetrics: async () => {
    set({ metricsLoading: true })
    try {
      const { activePlatform, dateRange } = get()
      const data = await api.metrics.get(activePlatform, dateRange)
      set({ metrics: data, metricsLoading: false })
    } catch {
      set({ metricsLoading: false })
    }
  },
}))
```

### Store 之间的通信模式

Store 之间不要直接互相 import 调用。如果 A store 的变更需要触发 B store 的更新，用 Zustand 的 `subscribe`：

```typescript
// 在 app.tsx 的 useEffect 中统一注册
useEffect(() => {
  // 发布完成后刷新 dashboard
  const unsub = usePublishStore.subscribe(
    (s) => s.lastPublishResult,
    (result) => {
      if (result?.success) {
        useDashboardStore.getState().fetchMetrics()
      }
    }
  )
  return unsub
}, [])
```

---

## 平台适配层

桌面端 (Tauri) 和 Web 端能力不同，用适配层抹平差异：

```typescript
// platform/src/tauri.ts
import { invoke } from '@tauri-apps/api/core'
import { open, save } from '@tauri-apps/plugin-dialog'
import { readFile, writeFile } from '@tauri-apps/plugin-fs'

export const platform = {
  type: 'desktop' as const,

  async selectFile(filters?: string[]) {
    return open({ filters: [{ name: 'Files', extensions: filters ?? ['*'] }] })
  },

  async readFile(path: string) {
    return readFile(path)
  },

  async generateThumbnail(videoPath: string): Promise<string> {
    // 调用 Rust 侧的视频处理
    return invoke('generate_thumbnail', { path: videoPath })
  },

  async getSystemInfo() {
    return invoke('get_system_info')
  },
}
```

```typescript
// platform/src/web.ts
export const platform = {
  type: 'web' as const,

  async selectFile(filters?: string[]) {
    return new Promise<File | null>((resolve) => {
      const input = document.createElement('input')
      input.type = 'file'
      if (filters) input.accept = filters.map(f => `.${f}`).join(',')
      input.onchange = () => resolve(input.files?.[0] ?? null)
      input.click()
    })
  },

  async readFile(file: File) {
    return new Uint8Array(await file.arrayBuffer())
  },

  async generateThumbnail(videoUrl: string): Promise<string> {
    // Web 端用 canvas 截帧
    const video = document.createElement('video')
    // ... canvas drawImage fallback
  },

  async getSystemInfo() {
    return { platform: 'web', arch: navigator.userAgent }
  },
}
```

```typescript
// platform/src/index.ts
const isTauri = '__TAURI_INTERNALS__' in window

export const platform = isTauri
  ? (await import('./tauri')).platform
  : (await import('./web')).platform
```

---

## ReactFlow 画布性能规范

在 `packages/canvas` 中统一执行：

```typescript
// nodes/base-node.tsx — 所有节点基类，强制 memo
import { memo } from 'react'
import { Handle, Position, type NodeProps } from '@xyflow/react'

function BaseNodeComponent({ data, selected }: NodeProps) {
  return (
    <div className={`rounded-lg border px-3 py-2 ${selected ? 'ring-2 ring-blue-500' : ''}`}>
      <Handle type="target" position={Position.Top} />
      <div className="text-sm font-medium">{data.label}</div>
      {data.subtitle && <div className="text-xs text-gray-500">{data.subtitle}</div>}
      <Handle type="source" position={Position.Bottom} />
    </div>
  )
}

export const BaseNode = memo(BaseNodeComponent)
```

```typescript
// workflow-canvas.tsx — 画布主组件
import { useCallback, useMemo } from 'react'
import { ReactFlow, Background, Controls, MiniMap } from '@xyflow/react'
import { useCanvasStore } from '@creator-os/stores'
import { nodeTypes } from './nodes'

export function WorkflowCanvas() {
  const nodes = useCanvasStore((s) => s.nodes)
  const edges = useCanvasStore((s) => s.edges)
  const onNodesChange = useCanvasStore((s) => s.onNodesChange)
  const onEdgesChange = useCanvasStore((s) => s.onEdgesChange)
  const onConnect = useCanvasStore((s) => s.onConnect)

  // nodeTypes 必须 memo 或定义在组件外，否则每次渲染都重建
  const memoNodeTypes = useMemo(() => nodeTypes, [])

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={memoNodeTypes}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      onlyRenderVisibleElements   // 超出视口的不渲染
      fitView
    >
      <Background />
      <Controls />
      <MiniMap pannable zoomable />
    </ReactFlow>
  )
}
```

关键性能规则：

- `nodeTypes` / `edgeTypes` 在组件外定义或用 `useMemo`，绝对不能每次 render 创建新对象
- 所有自定义节点组件用 `React.memo` 包裹
- 传给 `<ReactFlow>` 的函数全用 `useCallback`（如果不用 Zustand 直接返回的 stable reference）
- 从 store 只取需要的字段（如 `s => s.nodes`），不要 `s => s` 整体取
- 节点数 < 500 的场景不需要 semantic zooming，`onlyRenderVisibleElements` 足够

---

## WebSocket 实时事件

后端通过 WebSocket 推送事件（爬虫完成、Agent 分析结果、发布状态），前端统一接收并分发到对应 store：

```typescript
// api/src/ws.ts
import { useNotificationStore } from '@creator-os/stores'
import { useDashboardStore } from '@creator-os/stores'
import { usePublishStore } from '@creator-os/stores'

class EventSocket {
  private ws: WebSocket | null = null
  private reconnectTimer: number | null = null

  connect(url: string) {
    this.ws = new WebSocket(url)

    this.ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      this.dispatch(msg)
    }

    this.ws.onclose = () => {
      this.reconnectTimer = window.setTimeout(() => this.connect(url), 3000)
    }
  }

  private dispatch(msg: { type: string; payload: unknown }) {
    switch (msg.type) {
      case 'metric.updated':
        useDashboardStore.getState().fetchMetrics()
        break
      case 'agent.result':
        useNotificationStore.getState().addNotification(msg.payload)
        break
      case 'publish.status':
        usePublishStore.getState().updateStatus(msg.payload)
        break
    }
  }

  disconnect() {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer)
    this.ws?.close()
  }
}

export const eventSocket = new EventSocket()
```

---

## 构建与部署

```jsonc
// turbo.json
{
  "tasks": {
    "build": {
      "dependsOn": ["^build"],
      "outputs": ["dist/**"]
    },
    "dev": {
      "dependsOn": ["^build"],
      "cache": false,
      "persistent": true
    },
    "lint": {},
    "typecheck": {}
  }
}
```

```yaml
# pnpm-workspace.yaml
packages:
  - 'apps/*'
  - 'packages/*'
```

开发流程：

- `pnpm dev:desktop` → 启动 Vite + Tauri dev（热更新）
- `pnpm dev:web` → 启动 Vite dev server（纯 Web）
- `pnpm build:desktop` → Vite build + `tauri build`（生成 .dmg / .msi）
- `pnpm build:web` → Vite build（部署到 CDN / Nginx）

Tauri 打包配置要点（`tauri.conf.json`）：

```jsonc
{
  "productName": "Creator OS",
  "identifier": "com.creatoros.app",
  "build": {
    "beforeBuildCommand": "pnpm build",
    "frontendDist": "../dist"
  },
  "app": {
    "withGlobalTauri": false,
    "windows": [
      {
        "title": "Creator OS",
        "width": 1440,
        "height": 900,
        "minWidth": 1024,
        "minHeight": 680
      }
    ]
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": ["icons/icon.icns", "icons/icon.ico", "icons/icon.png"]
  }
}
```
