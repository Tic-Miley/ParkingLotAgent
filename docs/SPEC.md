# 停车场 AI Agent 仿真演示系统 — 技术规范

> 版本 1.0 | 2026-06-07 | 基于 4 轮深度访谈

---

## 1. 项目概述

### 1.1 核心目标

构建一个仿真停车场对话系统，验证以下技术点：

1. **AI Agent 自主决策**：Agent 理解自然语言问题 → 选择合适的工具 → 执行查询 → 综合数据生成回答
2. **多模态回答**：文本解释 + 统计图表（饼图、折线图）同框展示
3. **流式交互体验**：逐 token 输出文本，工具调用过程可视化，图表占位→填充
4. **本地数据闭环**：本地 SQLite 存储模拟数据，Agent 通过参数化工具+受控 SQL 查询

### 1.2 演示场景（至少实现）

| 用户问题 | 期望回答 |
|----------|----------|
| "现在停车场还剩多少车位？" | 文本：剩余 X 个，可以放心停车。图表：车位占用率仪表盘 |
| "现在停车场新能源车的比例？" | 文本：占比 X%。图表：扇形统计图（纯电/插混/燃油等） |
| "最近一个月停车数变化趋势？" | 文本：解释变化趋势。图表：折线统计图（每日停车数+7日均线） |

---

## 2. 架构总览

```
┌─────────────────────────────────────────────────────────┐
│                      Frontend (React)                     │
│  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │
│  │ Chat UI │  │ Markdown │  │ ECharts  │  │ToolCall  │ │
│  │ (bubble)│  │ Renderer│  │ (pie/line)│  │  Card    │ │
│  └────┬────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘ │
│       │            │             │              │        │
│       └────────────┴─────────────┴──────────────┘        │
│                        │  SSE (4 event types)             │
├────────────────────────┼─────────────────────────────────┤
│                  FastAPI Backend (Python)                  │
│  ┌─────────────────────┼─────────────────────────────┐   │
│  │                 ReAct Agent Loop                    │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐ │   │
│  │  │ System   │  │ Tool     │  │ Response         │ │   │
│  │  │ Prompt   │  │ Executor │  │ Streaming        │ │   │
│  │  └──────────┘  └─────┬────┘  └──────────────────┘ │   │
│  │                      │                              │   │
│  │  Tool Registry: get_vacancy, get_nev_ratio,         │   │
│  │  get_trend, render_chart, sql_query (controlled)    │   │
│  └──────────────────────┼──────────────────────────────┘   │
│                         │                                   │
│              ┌──────────┴──────────┐                       │
│              │     SQLite DB       │                       │
│              │  (vehicle_records)  │                       │
│              └─────────────────────┘                       │
├────────────────────────────────────────────────────────────┤
│                     DeepSeek V4 API                         │
│            (OpenAI-compatible chat completions)             │
└────────────────────────────────────────────────────────────┘
```

### 2.2 数据流（一次完整对话）

```
用户输入 → React → POST /chat → FastAPI
  → ReAct Loop:
      LLM 决策 (tool_call | respond)
      ├─ tool_call → 执行工具 → 结果喂回 LLM → 继续循环
      └─ respond → SSE 流式输出：
          ├─ event:tool_call    (工具执行状态卡片)
          ├─ event:text         (逐 token 文本)
          ├─ event:chart        (ECharts option JSON)
          └─ event:done         (流结束 + token 用量)
  → React 消费 SSE → 更新 UI
```

---

## 3. 技术栈

| 层 | 技术 | 理由 |
|----|------|------|
| **LLM** | DeepSeek V4 (OpenAI 兼容 API) | 成本低，function calling 兼容 OpenAI 协议 |
| **Agent** | 手写 ReAct Loop (Python) | 规模小（3-8 个工具），手写比 LangChain 更透明可控 |
| **后端** | Python 3.11+ / FastAPI / SSE | 异步原生支持 SSE，Python LLM 生态最好 |
| **前端** | React 18 + TypeScript + Vite | 生态丰富，流式 UI 模式成熟 |
| **样式** | Tailwind CSS | 快速出 UI，AI 友好的 utility class |
| **图表** | ECharts 5 | 直接渲染 Agent 输出的 ECharts option JSON |
| **Markdown** | react-markdown + remark-gfm | 支持流式重渲染，含表格/代码块 |
| **数据库** | SQLite (WAL 模式) | 零配置，单文件，完美支持聚合查询 |
| **数据分析** | Pandas（按需） | 仅用于时间序列工具（趋势、移动平均） |
| **LLM SDK** | openai (Python) | DeepSeek 兼容 OpenAI SDK，直接使用 |

### 3.1 未引入的技术及理由

| 技术 | 不引入的理由 |
|------|-------------|
| LangChain / LlamaIndex | 工具数 < 10，框架抽象成本 > 收益；Demo 阶段手写更透明 |
| Chart DSL 中间层 | 仅 2-3 种图表类型，DSL 设计+映射成本远超 token 节省收益 |
| Redis / 消息队列 | 单用户 Demo，无需异步任务队列 |
| Docker（可选） | 用户选择本地开发运行，Docker Compose 作为可选附录 |

---

## 4. 数据模型

### 4.1 SQLite Schema

```sql
-- 停车场配置（单停车场场景）
CREATE TABLE parking_lot_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),  -- 单行配置
    name TEXT NOT NULL DEFAULT 'Demo停车场',
    total_spots INTEGER NOT NULL DEFAULT 800,
    floors INTEGER NOT NULL DEFAULT 4,
    spots_per_floor INTEGER NOT NULL DEFAULT 200,
    hourly_rate REAL NOT NULL DEFAULT 6.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);

-- 车辆进出流水表
CREATE TABLE vehicle_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate TEXT NOT NULL,                          -- 车牌号
    vehicle_type TEXT NOT NULL                    -- 车辆类型
        CHECK(vehicle_type IN ('ICE', 'BEV', 'PHEV', 'HEV')),
    -- ICE  = 燃油车 (Internal Combustion Engine)
    -- BEV  = 纯电动 (Battery Electric Vehicle)
    -- PHEV = 插电混动 (Plug-in Hybrid Electric Vehicle)
    -- HEV  = 油电混动 (Hybrid Electric Vehicle, 非插电)
    entry_time DATETIME NOT NULL,                 -- 进入时间
    exit_time DATETIME,                           -- 离开时间 (NULL = 在场)
    entry_floor INTEGER CHECK(entry_floor BETWEEN 1 AND 10),
    entry_spot INTEGER                            -- 分配的车位号
);

-- 索引
CREATE INDEX idx_entry_time ON vehicle_record(entry_time);
CREATE INDEX idx_exit_time ON vehicle_record(exit_time);
CREATE INDEX idx_vehicle_type ON vehicle_record(vehicle_type);
CREATE INDEX idx_plate ON vehicle_record(plate);
CREATE INDEX idx_active ON vehicle_record(entry_time)
    WHERE exit_time IS NULL;                      -- 部分索引：仅在场车辆
```

### 4.2 车辆类型定义

| 代码 | 名称 | 新能源归类 | 说明 |
|------|------|-----------|------|
| `ICE` | 燃油车 | 否 | 传统汽油/柴油车 |
| `BEV` | 纯电动 | 是 | 完全电池驱动 |
| `PHEV` | 插电混动 | 是 | 可外部充电的混合动力 |
| `HEV` | 油电混动 | 是（部分统计） | 非插电混合动力，展示时归入"新能源"类 |

> **业务定义**：查询"新能源车比例"时，默认 BEV + PHEV 归类为新能源。HEV 是否计入通过 `get_nev_ratio(include_hev: bool = False)` 参数控制。

### 4.3 数据生成参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| 历史跨度 | 120 天 | 预生成 4 个月历史流水 |
| 总车位数 | 800 | 4 层 × 200 车位 |
| 日均车流量 | 1200-1800 辆次 | 随机波动 |
| 车辆类型分布 | ICE:55%, BEV:25%, PHEV:12%, HEV:8% | 模拟当前城市分布 |
| 时间模式 | 见下表 | 基于真实停车场行为 |

**时间模式模拟**：

| 时段 | 进场特征 | 出场特征 | 占用率 |
|------|---------|---------|--------|
| 早高峰 7:00-9:00 | 密集进入 | 少量离开 | 快速上升至 70% |
| 午间 11:00-14:00 | 中等进入 | 中等离开 | 波动 |
| 晚高峰 17:00-19:00 | 密集进入 | 少量离开 | 升至峰值 85-95% |
| 夜间 21:00-6:00 | 极少进入 | 极少离开 | 缓慢下降 |
| 周末/节假日 | 进入减少 30% | 模式不变 | 整体降低 15-20% |

**数据生成器实现**：`backend/data_generator.py`，使用泊松分布模拟车辆到达，指数分布模拟停车时长。首次运行时自动检测空数据库并填充。

---

## 5. 工具体系

### 5.1 工具注册格式（与 OpenAI Function Calling 兼容）

```python
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_current_vacancy",
        "description": "查询停车场当前的空余车位数和占用情况",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    }
}
```

### 5.2 核心工具定义

#### T1: `get_current_vacancy`
- **参数**：无
- **查询**：`SELECT COUNT(*) FROM vehicle_record WHERE exit_time IS NULL`
- **返回**：`{total_spots, occupied, vacant, vacancy_rate: float, last_updated: datetime}`
- **场景**："还有多少车位？"

#### T2: `get_nev_ratio`
- **参数**：`include_hev: bool = False`
- **查询**：分组计数在场车辆的 vehicle_type
- **返回**：`{total_parked, nev_count, nev_ratio, breakdown: [{type, count, percentage}]}`
- **场景**："新能源车占比多少？"

#### T3: `get_trend`
- **参数**：`days: int = 30`
- **查询**：按日聚合 entry_count, exit_count, peak_occupancy（当天最大同时在场数）
- **分析**（Pandas 按需）：
  - 计算每日同时在场峰值
  - 7 日移动平均 `df['peak_occupancy'].rolling(7).mean()`
  - 日环比变化率
- **返回**：`[{date, entry_count, exit_count, peak_occupancy, occupancy_rate, rolling_avg_7d}]`
- **场景**："最近一个月趋势？"

#### T4: `get_floor_status`
- **参数**：`floor: int | None = None`（None = 所有楼层）
- **查询**：按楼层分组统计在场车辆
- **返回**：`[{floor, total_spots, occupied, vacant, occupancy_rate}]`
- **场景**："3 楼还有位置吗？"

#### T5: `get_hourly_distribution`
- **参数**：`date: str | None = None`（None = 今天）
- **查询**：按小时统计进出车辆数
- **返回**：`[{hour: 0-23, entry_count, exit_count, net_change}]`
- **场景**："今天哪个时段车最多？"

#### T6: `get_vehicle_detail`
- **参数**：`plate: str`
- **查询**：按车牌精确查询最近的进出记录
- **返回**：`{plate, vehicle_type, current_status: 'parked'|'left', entry_time, exit_time, duration_minutes, floor, spot}`
- **场景**："查一下 京A12345 还在吗？"

#### T7: `get_summary_stats`
- **参数**：`days: int = 7`
- **查询**：最近 N 天的汇总统计（总车次、平均停车时长、平均占用率、新能源占比趋势）
- **返回**：`{total_visits, avg_duration_minutes, avg_occupancy_rate, nev_ratio_trend: [{date, ratio}]}`
- **场景**："这周整体情况怎么样？"

### 5.3 受控 SQL 工具

#### T8: `sql_query`
- **参数**：`query: str`（仅 SELECT）
- **安全约束**：
  - 只读连接（`PRAGMA query_only = ON`）
  - SQL 关键字黑名单：`DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, ATTACH, DETACH, VACUUM, PRAGMA`
  - 查询超时：5 秒（`timeout=5`）
  - 返回行数上限：1000 行
  - 禁止语句级 PRAGMA
- **错误处理**：安全违规返回具体原因，SQL 错误返回友好消息
- **降级策略**：此工具描述中包含"优先使用预定义函数，仅在预定义函数无法满足需求时使用 SQL 查询"

### 5.4 图表工具

#### T9: `render_chart`
- **参数**：`option: object`（完整的 ECharts option JSON）
- **验证**：
  - JSON Schema 校验（必须有 `series` 数组，每个 series 必须有 `type`）
  - 图表类型限制为 `pie`, `line`, `bar`
  - 数据点数量限制：饼图 ≤ 20 个扇区，折线图/柱状图 ≤ 200 个数据点
- **行为**：验证通过后通过 SSE `chart` 事件推送到前端
- **返回**：`{status: 'rendered', chart_type, data_points}`
- **说明**：此工具在 System Prompt 中被描述为首选图表生成方式；Agent 应在收集数据后调用它

---

## 6. Agent 循环（ReAct Loop）

### 6.1 核心算法

```python
async def agent_loop(user_message: str, history: list[dict], send_sse: Callable):
    messages = build_messages(system_prompt, history, user_message)

    for iteration in range(MAX_ITERATIONS):  # MAX_ITERATIONS = 8
        response = await llm.chat.completions.create(
            model=DEEPSEEK_MODEL,
            messages=messages,
            tools=ALL_TOOLS,
            tool_choice="auto",
            stream=False,  # 工具决策阶段不流式
        )

        assistant_msg = response.choices[0].message

        if assistant_msg.tool_calls:
            # 工具调用阶段
            messages.append(assistant_msg)

            for tool_call in assistant_msg.tool_calls:
                # 通知前端：工具开始执行
                await send_sse("tool_call", {
                    "tool_name": tool_call.function.name,
                    "status": "running",
                    "arguments": json.loads(tool_call.function.arguments)
                })

                try:
                    result = await execute_tool(tool_call)
                    await send_sse("tool_call", {
                        "tool_name": tool_call.function.name,
                        "status": "done",
                        "result_preview": truncate(result, 200)  # 截断长结果
                    })
                except ToolError as e:
                    result = {"error": str(e)}
                    await send_sse("tool_call", {
                        "tool_name": tool_call.function.name,
                        "status": "error",
                        "error": str(e)
                    })

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False)
                })

        else:
            # 文本响应阶段：流式输出
            stream = await llm.chat.completions.create(
                model=DEEPSEEK_MODEL,
                messages=messages,
                stream=True,
            )

            full_response = ""
            async for chunk in stream:
                if chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    await send_sse("text", {"token": token})

            # 检查响应中是否包含图表标记
            chart_blocks = extract_chart_blocks(full_response)
            for chart in chart_blocks:
                await send_sse("chart", {
                    "chart_id": chart.id,
                    "option": chart.option
                })

            messages.append({
                "role": "assistant",
                "content": full_response
            })

            await send_sse("done", {
                "usage": response.usage.model_dump() if hasattr(response, 'usage') else None
            })
            return

    # 超过最大迭代次数
    raise MaxIterationsError("Agent 未能在限定轮次内完成回答")
```

### 6.2 关键设计决策

| 决策 | 选择 | 理由 |
|------|------|------|
| 工具决策阶段 | 非流式 | 工具调用必须完整 JSON，流式无收益 |
| 文本响应 | 流式（SSE） | 核心体验指标 |
| 最大迭代 | 8 轮 | 实际不超过 3-4 轮（问→查→答），8 轮安全上限 |
| 工具结果截断 | 200 字符预览 | 全量结果在 tool message 中，SSE 只发预览 |
| 图表生成方式 | `render_chart` 工具 | 标准化——Agent 收集数据后显式调用 |

### 6.3 上下文窗口管理

DeepSeek V4 上下文窗口为 128K tokens。Demo 对话预计每轮 200-600 tokens，20 轮对话 + 工具结果 < 50K tokens，无须特殊管理。

**安全边际**：当累计消息超过 80K tokens 时，在 System Prompt 中注入提醒（非自动截断，保留完整上下文以便 Demo 验证）。

---

## 7. SSE 协议规范

### 7.1 端点

```
POST /api/chat
Content-Type: application/json
Accept: text/event-stream

Request:
{
  "message": "现在停车场还剩多少车位？",
  "conversation_id": "conv_abc123"  // 可选，用于多轮对话
}

Response: text/event-stream (SSE)
```

### 7.2 事件类型

#### `event: tool_call`
工具执行状态通知。

```json
// status = "running" | "done" | "error"
{
  "tool_name": "get_current_vacancy",
  "status": "running",
  "arguments": {},
  "message": "正在查询当前车位..."
}
```

```json
{
  "tool_name": "get_current_vacancy",
  "status": "done",
  "result_preview": {"vacant": 123, "total_spots": 800}
}
```

```json
{
  "tool_name": "sql_query",
  "status": "error",
  "error": "查询超时（> 5秒），请缩小查询范围"
}
```

#### `event: text`
增量文本 token。

```json
{
  "token": "现在"
}
```

前端按顺序拼接 token 并用 react-markdown 渲染。

#### `event: chart`
图表数据（ECharts option JSON）。

```json
{
  "chart_id": "chart_abc123",
  "chart_type": "pie",
  "option": {
    "title": {"text": "新能源车占比", "left": "center"},
    "tooltip": {"trigger": "item"},
    "series": [{
      "type": "pie",
      "radius": "60%",
      "data": [
        {"name": "纯电动", "value": 45},
        {"name": "插电混动", "value": 30},
        {"name": "燃油车", "value": 125}
      ]
    }]
  }
}
```

**图表渲染时序**：
1. Agent 在文本响应中提及"下面是统计图"
2. Agent 调用 `render_chart` 工具 → 前端收到 `chart` 事件
3. 前端在消息气泡下方渲染 ECharts 实例
4. 图表有进入动画（`animationDuration: 800`）

#### `event: done`
流结束。

```json
{
  "status": "completed",
  "usage": {
    "prompt_tokens": 1240,
    "completion_tokens": 350,
    "total_tokens": 1590
  }
}
```

#### `event: error`
全局错误。

```json
{
  "code": "LLM_UNAVAILABLE",
  "message": "AI 服务暂时不可用，请稍后重试",
  "retryable": true
}
```

### 7.3 前端 SSE 消费

```typescript
// hooks/useSSE.ts
function useChat() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [isStreaming, setIsStreaming] = useState(false);

  async function sendMessage(text: string) {
    const userMsg: Message = { role: 'user', content: text };
    const assistantMsg: Message = { role: 'assistant', content: '', toolCalls: [], charts: [] };
    setMessages(prev => [...prev, userMsg, assistantMsg]);
    setIsStreaming(true);

    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });

    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    // SSE parsing loop...
    // On 'text' event: append token to assistantMsg.content
    // On 'tool_call' event: add/update ToolCallCard
    // On 'chart' event: add chart to assistantMsg.charts
    // On 'done' event: setIsStreaming(false)
    // On 'error' event: show error toast
  }

  return { messages, isStreaming, sendMessage };
}
```

---

## 8. System Prompt 设计

### 8.1 完整 Prompt（中文）

```
你是一个停车场数据分析助手。你拥有以下能力：

1. 查询停车场实时状态（空余车位、占用率）
2. 分析车辆类型分布（燃油车、纯电动、插电混动、油电混动）
3. 统计历史趋势（日/周/月维度的停车数变化）
4. 生成统计图表（饼图、折线图、柱状图）

## 工作原则

- 使用工具获取数据，不要编造数字
- 回答简洁专业，先给结论再给细节
- 当数据适合可视化时，调用 render_chart 工具生成图表
- 饼图用于展示占比（如车辆类型分布）
- 折线图用于展示趋势（如每日停车数变化）
- 柱状图用于对比（如各楼层占用率）
- 图表配色使用协调的颜色方案

## 数据说明

- 停车场共 800 个车位，4 层楼
- 新能源车包括：纯电动(BEV)、插电混动(PHEV)、油电混动(HEV)
- 车辆类型代码：ICE=燃油车, BEV=纯电动, PHEV=插电混动, HEV=油电混动
- 当前时间：{current_datetime}

## 图表生成规范

生成 ECharts option 时遵循：
- title.text 简洁明了
- 饼图使用 radius: "60%" 环形样式
- 折线图使用 smooth: true 平滑曲线
- 颜色使用 ['#3b82f6', '#10b981', '#f59e0b', '#ef4444', '#8b5cf6', '#06b6d4']
- tooltip 始终包含
- 不需要 legend（数据类别少）

## 错误处理

- 如果工具返回错误，如实告知用户并建议替代方案
- 如果数据不足（如查询时间范围超出数据覆盖范围），说明可用数据范围
```

### 8.2 Few-Shot 示例（嵌入 Prompt）

```
## 对话示例

用户：现在还剩多少车位？
助手：让我查询一下当前车位情况。
[调用 get_current_vacancy]
查询结果显示：总车位800个，已占用652个，剩余**148个**车位，占用率81.5%。目前停车位充足，可以放心停车。
[调用 render_chart 生成占用率仪表盘]

用户：新能源车多吗？
助手：我来看看当前停车场内新能源车的情况。
[调用 get_nev_ratio]
当前停车场内共652辆车，其中新能源车（BEV+PHEV+HEV）共**287辆**，占比**44.0%**。
[调用 render_chart 生成饼图]
```

---

## 9. 前端设计

### 9.1 组件树

```
App
└── ChatLayout
    ├── Header (标题栏: "🅿️ 停车场 AI 助手")
    ├── MessageList (消息列表, overflow-y: auto)
    │   ├── UserMessage
    │   │   └── Bubble (右对齐, 蓝色背景)
    │   └── AssistantMessage
    │       ├── ToolCallCard[] (可折叠, 显示工具名+状态)
    │       │   ├── Icon (⏳/✅/❌)
    │       │   ├── Label ("正在查询车位..." / "查询完成")
    │       │   └── Detail (折叠区: 参数/结果摘要)
    │       ├── MarkdownBody (react-markdown 渲染)
    │       └── ChartWidget[] (ECharts 实例)
    ├── ChatInput
    │   ├── Textarea (自动增高, Enter 发送, Shift+Enter 换行)
    │   ├── SendButton (流式时变为 StopButton)
    │   └── CharCount (可选)
    ├── QuickQuestions (快捷问题按钮组)
    │   ├── "还剩多少车位？"
    │   ├── "新能源车占比？"
    │   └── "最近30天趋势？"
    └── EmptyState (无消息时的欢迎界面)
        ├── Logo / 图标
        ├── 欢迎语
        └── 功能简介卡片
```

### 9.2 状态管理

```typescript
interface ChatState {
  messages: Message[];
  isStreaming: boolean;
  error: string | null;
  conversationId: string | null;
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;              // Markdown 字符串
  toolCalls: ToolCallEvent[];   // 工具调用记录
  charts: ChartData[];          // ECharts option 数组
  timestamp: number;
  isStreaming: boolean;         // 仅 assistant 消息
}

interface ToolCallEvent {
  toolName: string;
  status: 'running' | 'done' | 'error';
  arguments?: Record<string, unknown>;
  resultPreview?: string;
  error?: string;
}

interface ChartData {
  chartId: string;
  chartType: 'pie' | 'line' | 'bar';
  option: EChartsOption;
}
```

### 9.3 样式设计原则

- **设计风格**：简洁现代，白色背景 + 微阴影卡片
- **配色**：主色 `#3b82f6`（蓝），辅色 `#10b981`（绿），背景 `#f8fafc`
- **消息气泡**：用户蓝底白字（右对齐），助手白底黑字（左对齐）+ 边框
- **ToolCallCard**：左侧色带（running=蓝动画, done=绿, error=红），默认折叠
- **图表容器**：白色卡片，圆角 12px，阴影 `0 1px 3px rgba(0,0,0,0.1)`
- **响应式**：最大宽度 800px 居中，移动端全宽
- **字体**：系统默认中文字体（`-apple-system, PingFang SC, Microsoft YaHei`）

### 9.4 关键交互

| 交互 | 行为 |
|------|------|
| 发送消息 | 输入框清空，立即显示用户气泡+助手占位气泡（含骨架屏） |
| 流式接收 | 助手气泡内容逐字增长，自动滚到底部（用户手动上滚时不强制） |
| 工具调用 | ToolCallCard 在助手气泡上方出现，status 实时更新，可点击展开详情 |
| 图表渲染 | ChartWidget 在文本下方以动画形式出现（ECharts `animationDuration: 800`） |
| 生成中断 | 流式过程中点击 Stop 按钮 → 关闭 SSE 连接 → 助手气泡标记为"已中断" |
| 复制消息 | 每条助手消息右上角复制按钮（hover 显示） |
| 快捷问题 | 点击预设问题自动填入输入框并发送 |

---

## 10. 错误处理矩阵

| 错误来源 | 错误类型 | 用户看到的消息 | 处理逻辑 |
|----------|---------|---------------|---------|
| LLM API 不可用 | 网络/服务故障 | "AI 服务暂时不可用，请稍后重试" + 重试按钮 | 重试 2 次（间隔 2s, 5s），失败后前端置 error 状态 |
| LLM 返回非标准格式 | tool_call JSON 解析失败 | "处理请求时遇到问题，请重新表述" | catch JSONDecodeError → 发送原始错误给 LLM 自修正（1 次机会） |
| 工具执行超时 | SQLite 查询 > 5s | "查询超时，请尝试缩小查询范围" | 工具返回错误 → 喂回 Agent → Agent 调整策略或告知用户 |
| SQL 安全检查失败 | 用户问题触发受控 SQL 的黑名单 | "此查询涉及不允许的操作" | 拒绝执行，Agent 应使用预定义工具替代 |
| 工具参数错误 | 参数类型/范围不符 | 工具返回具体参数错误 | 错误信息喂回 Agent → Agent 修正参数后重试 |
| 数据为空 | 查询结果 0 行 | "当前无相关数据" + 上下文说明 | 正常返回空结果，Agent 如实描述 |
| SSE 连接中断 | 网络波动 | 前端自动重连（EventSource 默认行为） | 重连后后端需支持断点续传（或放弃当前消息，提示用户重发） |
| 上下文超长 | 对话超过 80K tokens | 会话开始前注入提醒："当前对话较长，建议开启新会话" | 前端显示提醒条，用户可选择继续或新建 |

### 10.1 错误处理原则

1. **永远不让用户看到原始技术错误**——所有错误经过包装
2. **区分可恢复和不可恢复**——可恢复的提示重试，不可恢复的建议新会话
3. **Agent 错误自修复**——工具调用失败时错误信息会喂回 LLM，给它一次修正机会
4. **快速失败**——2 次重试 + 1 次自修正仍未解决 → 给出友好错误消息，不陷入死循环

---

## 11. 项目文件结构

```
parking-lot/
├── backend/
│   ├── main.py                 # FastAPI 入口 + CORS + SSE endpoint
│   ├── config.py               # 配置（API key, DB path, model name）
│   ├── agent.py                # ReAct Agent 循环
│   ├── tools/
│   │   ├── __init__.py         # Tool registry（ALL_TOOLS 列表）
│   │   ├── parking.py          # T1-T7 停车场业务工具
│   │   ├── sql_tool.py         # T8 受控 SQL 查询
│   │   └── chart_tool.py       # T9 图表渲染 + ECharts 校验
│   ├── db.py                   # SQLite 连接管理 + 初始化
│   ├── data_generator.py       # 模拟数据生成器
│   ├── models.py               # Pydantic 模型（请求/响应/SSE事件）
│   ├── sse.py                  # SSE 事件发送器
│   └── requirements.txt        # Python 依赖
├── frontend/
│   ├── src/
│   │   ├── App.tsx
│   │   ├── main.tsx
│   │   ├── index.css           # Tailwind 入口
│   │   ├── components/
│   │   │   ├── ChatLayout.tsx
│   │   │   ├── Header.tsx
│   │   │   ├── MessageList.tsx
│   │   │   ├── UserMessage.tsx
│   │   │   ├── AssistantMessage.tsx
│   │   │   ├── ToolCallCard.tsx
│   │   │   ├── ChartWidget.tsx
│   │   │   ├── ChatInput.tsx
│   │   │   ├── QuickQuestions.tsx
│   │   │   └── EmptyState.tsx
│   │   ├── hooks/
│   │   │   └── useChat.ts      # SSE 消费 + 消息状态管理
│   │   ├── types/
│   │   │   └── chat.ts         # TypeScript 类型定义
│   │   └── utils/
│   │       └── echarts.ts      # ECharts 主题默认配置
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.js
│   └── postcss.config.js
├── data/
│   └── .gitkeep                # SQLite DB 存储目录
├── .env.example                # 环境变量模板
├── .gitignore
├── README.md
└── SPEC.md                     # 本文件
```

---

## 12. 开发环境 & 运行

### 12.1 环境变量

```bash
# .env（从 .env.example 复制）
DEEPSEEK_API_KEY=sk-xxxx
DEEPSEEK_BASE_URL=https://api.deepseek.com/v1   # 或代理地址
DEEPSEEK_MODEL=deepseek-chat
DATABASE_PATH=./data/parking_lot.db
```

### 12.2 启动命令

```bash
# 1. 后端
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
python data_generator.py  # 首次：生成模拟数据
uvicorn main:app --reload --port 8000

# 2. 前端
cd frontend
npm install
npm run dev               # Vite dev server, port 5173

# 3. 浏览器打开 http://localhost:5173
```

### 12.3 Python 依赖 (`requirements.txt`)

```
fastapi==0.115.0
uvicorn[standard]==0.30.0
openai==1.50.0           # DeepSeek 兼容 OpenAI SDK
pandas==2.2.0
pydantic==2.9.0
python-dotenv==1.0.1
sse-starlette==2.1.0
```

### 12.4 前端依赖 (`package.json`)

```json
{
  "dependencies": {
    "react": "^18.3.0",
    "react-dom": "^18.3.0",
    "react-markdown": "^9.0.0",
    "remark-gfm": "^4.0.0",
    "echarts": "^5.5.0",
    "echarts-for-react": "^3.0.0"
  },
  "devDependencies": {
    "@types/react": "^18.3.0",
    "typescript": "^5.5.0",
    "vite": "^5.4.0",
    "tailwindcss": "^3.4.0",
    "postcss": "^8.4.0",
    "autoprefixer": "^10.4.0"
  }
}
```

---

## 13. 实现路线图

### Phase 1：数据基础（第 1 天）
- [ ] SQLite Schema 创建 (`db.py`)
- [ ] 数据生成器 (`data_generator.py`)
  - [ ] 车辆流水生成（泊松到达+指数停车时长）
  - [ ] 早晚高峰模式 + 周末效应
  - [ ] 车辆类型按设定比例分配
- [ ] 验证：运行生成器，SQLite 中有 120 天历史数据

### Phase 2：工具函数（第 1-2 天）
- [ ] Tool schema 定义（OpenAI function calling JSON 格式）
- [ ] T1-T7 停车场业务工具实现
- [ ] T8 受控 SQL 工具 + 安全检查
- [ ] T9 图表渲染工具 + ECharts option 校验
- [ ] 单元测试：每个工具的输入输出

### Phase 3：Agent 循环（第 2 天）
- [ ] DeepSeek API 集成（OpenAI SDK 配置）
- [ ] ReAct Loop 主循环
- [ ] 流式响应处理
- [ ] 工具结果→上下文格式化
- [ ] 测试：命令行下跑通三个核心问题

### Phase 4：后端 API（第 2-3 天）
- [ ] FastAPI `/api/chat` SSE 端点
- [ ] SSE 事件发送器（4 种事件类型）
- [ ] CORS 配置（开发环境）
- [ ] 错误处理中间件
- [ ] 测试：curl 请求验证 SSE 输出

### Phase 5：前端核心（第 3-4 天）
- [ ] Vite + React + Tailwind 项目初始化
- [ ] ChatLayout / MessageList 布局
- [ ] SSE 消费 Hook (`useChat`)
- [ ] UserMessage / AssistantMessage 组件
- [ ] ChatInput（含 Stop 按钮）
- [ ] EmptyState 欢迎页
- [ ] 流式 Markdown 渲染

### Phase 6：图表 + 可视化（第 4 天）
- [ ] ChartWidget 组件（ECharts 集成）
- [ ] ToolCallCard（折叠卡片 + 动画状态）
- [ ] QuickQuestions 预设按钮
- [ ] 图表占位→填充→动画流程

### Phase 7：打磨（第 5 天）
- [ ] 错误状态 UI（错误 toast + 重试按钮）
- [ ] 自动滚动到底部（智能：用户手动上滚时不强制）
- [ ] 消息复制功能
- [ ] 响应式适配（移动端）
- [ ] README 编写
- [ ] 端到端 Demo 录制准备

---

## 14. 风险 & 缓解

| 风险 | 概率 | 影响 | 缓解措施 |
|------|------|------|----------|
| DeepSeek V4 function calling 稳定性不足 | 中 | 中 | 实现 JSON 解析兜底（正则提取 function name + arguments）；备选切 OpenAI GPT-4o |
| DeepSeek API 延迟高（> 5s 首 token） | 中 | 高 | 工具决策阶段显示 "正在思考..." 动画；设置 30s 超时 |
| LLM 生成的 ECharts option 不合法 | 高 | 中 | `render_chart` 工具内 JSON Schema 校验 + 默认值填充 + 错误修复（如缺失 `series.type` 自动补充） |
| 数据生成器模式与真实不符 | 低 | 低 | 不影响技术验证，仅影响 Demo 观感。可调参数 |
| SQLite 并发（后续多人） | 低 | 低 | 单用户 Demo 无此问题。开启 WAL 模式即可支持有限并发读 |
| SSE 在代理/防火墙环境被缓冲 | 中 | 中 | 设置响应头 `X-Accel-Buffering: no`；提供 REST 降级端点 |

---

## 15. 扩展方向（Phase 2，超出当前范围）

以下功能明确不在当前 Demo 范围内，但架构预留了扩展点：

- **多停车场对比**：parking_lot_config 已预留多行设计（当前限制单行）
- **实时车辆进出模拟**：WebSocket 推送模拟实时事件
- **用户认证 + 会话持久化**：对话历史存储到 SQLite 或文件
- **语音输入**：Web Speech API
- **深色模式**：Tailwind dark mode
- **Docker 部署**：Docker Compose 一键启动
- **多 LLM 对比模式**：切换模型对比回答质量
