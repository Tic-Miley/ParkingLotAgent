# 工具体系文档 v2

> 版本 2.0 | 2026-06-10 | 从场景驱动转向操作原语驱动

项目提供 **5 个工具**（4 核心 + 1 兜底），注册在 `TOOL_SCHEMAS`（LLM 看到的函数签名）和 `TOOL_EXECUTORS`（实际调度）两个字典中。

| # | 工具名 | 类型 | 说明 |
|---|--------|------|------|
| 1 | `get_config` | 配置查询 | 获取停车场全局配置 |
| 2 | `query_aggregation` | 聚合查询 | 通用参数化聚合（核心工具） |
| 3 | `get_vehicle` | 个体查询 | 按车牌查询车辆详情 |
| 4 | `render_chart` | 图表渲染 | 校验并生成 ECharts 图表 |
| 5 | `sql_query` | SQL兜底 | 受控只读SQL，覆盖边缘需求 |

---

## 一、`get_config` — 获取停车场配置

- **调用场景**：需要总车位数、楼层数、费率等全局上下文时
- **参数**：无
- **返回结构**：

```json
{
  "name": "Demo停车场",
  "total_spots": 800,
  "floors": 4,
  "spots_per_floor": 200,
  "hourly_rate": 6.0
}
```

---

## 二、`query_aggregation` — 通用聚合查询（核心工具）

一个工具覆盖绝大多数停车场数据分析场景。

**参数**：

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `active_only` | `boolean` | 否 | `true` | `true`=仅在场车辆，`false`=历史所有记录 |
| `group_by` | `string` | 否 | `null` | `null`(全局) / `"vehicle_type"` / `"floor"` / `"date"` / `"hour"` / `"day_of_week"` / `"month"` |
| `date_from` | `string` | 否 | — | 起始日期 `YYYY-MM-DD`，仅 `active_only=false` 时有效 |
| `date_to` | `string` | 否 | — | 结束日期 `YYYY-MM-DD`，仅 `active_only=false` 时有效 |
| `include_duration` | `boolean` | 否 | `false` | 是否计算平均停车时长，仅 `active_only=false` 时有效 |

**`active_only` 与 `group_by` 的约束**：

| active_only | 可用的 group_by | 说明 |
|-------------|----------------|------|
| `true` | `null`, `"vehicle_type"`, `"floor"` | 在场车辆没有时间维度 |
| `false` | 全部7种 | 历史数据可按任意维度分组 |

**典型调用场景**：

| 用户问题 | 调用方式 |
|----------|----------|
| "现在还有多少车位？" | `query_aggregation(active_only=true)` → 取 `vacant` |
| "当前各类型车辆占比？" | `query_aggregation(active_only=true, group_by="vehicle_type")` |
| "各楼层还有位吗？" | `query_aggregation(active_only=true, group_by="floor")` |
| "最近7天每日停车趋势？" | `query_aggregation(active_only=false, group_by="date", date_from="7天前")` |
| "今天各小时进出分布？" | `query_aggregation(active_only=false, group_by="hour", date_from="今天", date_to="今天")` |
| "最近30天总车次和平均时长？" | `query_aggregation(active_only=false, include_duration=true)` |
| "工作日vs周末对比？" | `query_aggregation(active_only=false, group_by="day_of_week")` |
| "月度趋势？" | `query_aggregation(active_only=false, group_by="month")` |

**返回结构（统一）** — `active_only=true, group_by="vehicle_type"` 示例：

```json
{
  "active_only": true,
  "group_by": "vehicle_type",
  "total_spots": 800,
  "occupied": 523,
  "vacant": 277,
  "occupancy_rate": 0.6538,
  "total": 523,
  "groups": [
    {
      "key": "ICE",
      "label": "燃油车",
      "count": 288,
      "ratio": 0.5507
    },
    {
      "key": "BEV",
      "label": "纯电动",
      "count": 131,
      "ratio": 0.2505
    }
  ],
  "date_range": null
}
```

**返回结构** — `active_only=false, group_by="date"` 示例：

```json
{
  "active_only": false,
  "group_by": "date",
  "total_spots": 800,
  "total": 10450,
  "groups": [
    {
      "date": "2026-06-01",
      "entry_count": 1452,
      "exit_count": 1398,
      "net_change": 54,
      "peak_occupancy_estimate": 1089,
      "occupancy_rate": 0.75,
      "rolling_avg_7d": 1123.5,
      "avg_duration_minutes": 178.3
    }
  ],
  "date_range": {"from": "2026-05-10", "to": "2026-06-09"}
}
```

**内置派生指标**：
- `ratio`, `vacant`, `occupancy_rate` — 自动计算
- `net_change = entry_count - exit_count` — 日期/小时分组时
- `peak_occupancy_estimate = entry_count × 0.75` — 日期分组时
- `rolling_avg_7d` — 日期分组时（pandas 计算）
- `avg_duration_minutes` — `include_duration=true` 时

---

## 三、`get_vehicle` — 车辆个体查询

- **调用场景**：用户问"查一下京A12345这辆车"、"某车牌的车停在哪"
- **参数**：`plate`（必填，字符串）
- **返回结构**：

```json
{
  "found": true,
  "plate": "京A00042",
  "vehicle_type": "BEV",
  "vehicle_type_name": "纯电动",
  "status": "parked",
  "entry_time": "2026-06-08 09:15:30",
  "exit_time": null,
  "duration_minutes": 317.5,
  "floor": 2,
  "spot": 87,
  "history_count": 15
}
```

- `found=false` 时返回 `{found: false, plate, error}`
- `status`：`"parked"`（在场）/ `"left"`（已离开）
- `history_count`：该车牌的历史总记录数
- 在场时 `duration_minutes` 基于入场到当前计算；已离开时基于进出差

---

## 四、`render_chart` — 图表渲染

- **参数**：`option`（完整 ECharts option JSON）
- **支持的图表类型**：`pie`（饼图）、`line`（折线图）、`bar`（柱状图）
- **验证规则**：饼图扇区 ≤20、线/柱图数据点 ≤200、series 非空
- **自动修复**：缺失的 tooltip/colors/radius/smooth
- **返回**：`{status: "rendered", chart_id, chart_type, data_points, option}`

---

## 五、`sql_query` — 受控只读 SQL（兜底）

- **调用场景**：仅当 `query_aggregation` 无法满足需求时使用（典型：二维交叉分组如"每天各类型占比"）
- **安全机制**：关键字黑名单、只读连接、1000行上限、5秒超时
- **返回**：`{columns, rows, row_count}`

---

## 工具调度流程

封装在 `agent.py` 的 `agent_loop()` 中：

```
用户问题 → DeepSeek V4（tool_choice="auto"）
  → LLM 返回 tool_calls
    → TOOL_EXECUTORS[tool_name](**args)
      → SSE: tool_call 事件（running → done/error）
      → 如果工具返回 chart 类型 → SSE: chart 事件
      → 工具结果作为 assistant message + tool role message 喂回 LLM
  → LLM 判断是否还需要更多工具调用（最多 8 轮 ReAct）
  → LLM 返回最终文本 → 流式 SSE text 事件
```

**设计原则**：

- `query_aggregation` 是**核心工具** —— 参数组合覆盖 90% 查询场景，LLM 无需记忆多个工具
- `sql_query` 是**兜底工具** —— 仅边缘需求使用，受严格安全约束
- `render_chart` 是**输出工具** —— 数据就绪后，LLM 决定用何种图表呈现
- 工具之间**正交无重叠** —— 每个需求只有一条合理的工具调用路径
