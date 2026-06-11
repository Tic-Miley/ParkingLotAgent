# 停车场工具体系重设计方案

> 版本 2.0 | 2026-06-09 | 从场景驱动转向操作原语驱动

---

## 一、数据库结构理解

停车场数据库由两张表构成：

### `parking_lot_config` — 全局单例配置（1行）

| 字段 | 说明 |
|------|------|
| `total_spots` | 总车位数，默认 800 |
| `floors` | 楼层数，默认 4 |
| `spots_per_floor` | 每层车位数，默认 200 |
| `hourly_rate` | 每小时停车费率，默认 6.0 元 |

### `vehicle_record` — 核心业务事件表（~18万行，120天）

| 字段 | 说明 |
|------|------|
| `plate` | 车牌号 |
| `vehicle_type` | 车辆能源类型：`ICE` / `BEV` / `PHEV` / `HEV` |
| `entry_time` | 入场时间（精确到秒） |
| `exit_time` | 离场时间；`NULL` = 至今未离场（在场） |
| `entry_floor` | 入场楼层（1–4） |
| `entry_spot` | 入场车位号（1–200） |

**关键索引**：`idx_entry_time`、`idx_exit_time`、`idx_vehicle_type`、`idx_plate`、`idx_active`（部分索引，仅覆盖 `exit_time IS NULL`）。

**核心语义**：每行是一个"停车事件"——一辆车在某个时间点进入，在某个时间点（或尚未）离开。所有分析本质上是对这个事件流在不同维度上的聚合。

---

## 二、需求边界分析

### 2.1 需求全景

从数据库结构出发，用户可能提出的所有问题可以按三个正交维度分类：

| 维度 | 取值 |
|------|------|
| **时间范围** | 当前快照 / 历史某日 / 自定义日期段 / 全量历史 |
| **分组粒度** | 全局 / 按车辆类型 / 按楼层 / 按时间（小时/日/周/月/星期几） |
| **指标类型** | 计数 / 占比 / 平均值（时长）/ 趋势 / 峰值 / 净变化 |

### 2.2 需求边界划定

**边界内（工具应直接覆盖）** — 描述性统计 + 基础对比：

- 当前状态：在场车辆数、空余车位、各类型占比、各楼层占用
- 历史趋势：按日/周/月的进出量、占用率变化、7日移动平均
- 时段分布：按小时的进出分布、高峰低谷识别
- 类型分析：各能源类型占比及趋势
- 个体查询：某车牌的历史和当前状态
- 汇总统计：总车次、平均停车时长、平均占用率
- 基础对比：工作日vs周末、自定义时间段对比（通过参数化实现）

**边界外（需 `sql_query` 兜底或超出数据能力）**：

- 二维交叉分组（如"每天各类型的占比趋势"）— 需 `sql_query`
- 预测性分析：未来趋势预测 — 需模型
- 异常检测：需统计算法
- 跨停车场对比：仅单停车场

---

## 三、现有工具体系的问题诊断

现有9个工具（T1-T7业务查询 + T8 `sql_query` + T9 `render_chart`）存在以下结构性问题：

### 3.1 功能重叠

| 重叠域 | 涉及工具 | 问题 |
|--------|---------|------|
| 在场统计 | T1（空余车位）、T2（新能源占比）、T4（楼层占用） | 三者都在查 `exit_time IS NULL`，只是分组维度不同 |
| 历史趋势 | T3（趋势）、T7（汇总统计） | T7 的 `avg_occupancy_rate` 与 T3 的 `occupancy_rate` 语义重叠 |
| 类型占比 | T2（当前新能源占比）、T7 的 `nev_ratio_trend` | T2 查当前，T7 查趋势，本质是同一操作不同时间范围 |

### 3.2 时间维度僵硬

- T1/T2/T4 只能查"当前"（硬编码 `exit_time IS NULL`）
- T3/T7 只能查"最近N天"（参数只是一个整数 days）
- 用户无法指定"2026年5月"或"上周一到周五"这样的自定义范围

### 3.3 工具膨胀与缺失并存

- 有6个业务查询工具，但缺少 `day_of_week`（星期几分组）、`month`（按月聚合）等基础维度
- 要获得"工作日vs周末对比"，LLM 必须通过 `sql_query` 手写 SQL

### 3.4 根本原因

现有设计是**场景驱动**而非**操作原语驱动**——每新增一个演示场景就加一个工具，导致功能边界模糊。正确的做法是：识别出数据库上最基本的操作类型，用参数化而非工具数量来覆盖场景。

---

## 四、新工具体系设计

### 4.1 设计原则

1. **操作原语驱动**：工具对应数据库上的基本操作类型，而非业务场景
2. **参数化扩展**：通过参数覆盖变体，而非新增工具
3. **正交性**：每个工具解决一类独立问题，工具之间无功能重叠
4. **LLM友好**：参数语义直观，返回结构统一，内置派生指标减少LLM计算负担
5. **最小集合**：核心工具 ≤ 4个，`sql_query` 作为兜底

### 4.2 工具清单

| # | 工具名 | 类型 | 说明 |
|---|--------|------|------|
| 1 | `get_config` | 配置查询 | 获取停车场全局配置 |
| 2 | `query_aggregation` | 聚合查询 | 通用参数化聚合，替代 T1-T5、T7 |
| 3 | `get_vehicle` | 个体查询 | 按车牌查询车辆详情 |
| 4 | `render_chart` | 图表渲染 | 校验并生成 ECharts 图表 |
| 5 | `sql_query` | SQL兜底 | 受控只读SQL，覆盖边缘需求 |

---

### 4.3 工具详细定义

#### 工具1：`get_config` — 获取停车场配置

```
无参数
返回：{name, total_spots, floors, spots_per_floor, hourly_rate}
```

**职责**：提供全局上下文。为其他工具和 LLM 推理提供基础参数（如计算"占用率"需要 total_spots）。独立存在是因为它是配置查询，与车辆事件查询在操作类型上正交。

---

#### 工具2：`query_aggregation` — 通用聚合查询（核心工具）

一个工具替代现有 T1（空余车位）、T2（新能源占比）、T3（趋势）、T4（楼层占用）、T5（时段分布）、T7（汇总统计）共6个工具。

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

**设计要点**：

- 工具内部自动 JOIN `parking_lot_config` 获取 `total_spots`，自动计算 `vacant`、`occupancy_rate`、`ratio` 等派生指标，减少 LLM 的计算负担
- `group_by="date"` 时自动计算 7 日移动平均（`rolling_avg_7d`）
- `peak_occupancy_estimate` 使用 `entry_count * 0.75` 估算，字段名标注为 estimate
- 当 `active_only=false` 且 `date_from` 未指定时，默认最近 30 天
- `group_by="hour"` 时自动补齐 0-23 小时（无数据填 0），计算 `net_change`
- `label` 字段提供中文名称映射（`ICE→燃油车`、`BEV→纯电动` 等）

---

#### 工具3：`get_vehicle` — 车辆个体查询

**参数**：

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `plate` | `string` | 是 | 车牌号 |

**返回结构**：

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

**设计要点**：

- 先查在场记录（`exit_time IS NULL`），再 fallback 到最近已离开记录
- `history_count` 是该车牌的总记录数，提供历史频次上下文
- 在场时 `duration_minutes` 基于入场到当前时间计算；已离开时基于进出时间差
- `status`：`"parked"`（在场）/ `"left"`（已离开）

---

#### 工具4：`render_chart` — 图表渲染

**参数**：`option`（完整 ECharts option JSON）

**职责**：校验图表类型（pie/line/bar）、数据点上限（饼图≤20扇区、线图/柱图≤200点）、自动修复缺失的 tooltip/colors/radius，返回 `{status, chart_id, chart_type, data_points, option}`。

与数据查询工具完全正交——它不关心数据从何而来，只负责将 ECharts option 渲染为前端图表。

---

#### 工具5（兜底）：`sql_query` — 受控只读 SQL

保持现有安全约束：
- 关键字黑名单（DROP/DELETE/UPDATE/INSERT/ALTER/CREATE/ATTACH/DETACH/VACUUM）
- 只读连接（`PRAGMA query_only = ON` + URI `mode=ro`）
- 1000行上限
- 5秒查询超时

**定位**：覆盖前4个工具无法满足的需求。典型场景是二维交叉分组（如"每天各类型占比趋势"），以及任意 `query_aggregation` 不支持的自定义聚合。

---

### 4.4 工具正交性验证

对于任意一个查询需求，是否存在唯一合理的工具调用路径？

| 用户问题 | 唯一工具路径 | 备选路径？ |
|----------|-------------|-----------|
| "现在还有多少车位？" | `query_aggregation(active_only=true)` → 取 `vacant` | 无 |
| "当前各类型车辆占比？" | `query_aggregation(active_only=true, group_by="vehicle_type")` | 无 |
| "2楼还有位吗？" | `query_aggregation(active_only=true, group_by="floor")` → 筛选 `key=2` | 无 |
| "最近7天每天的停车量趋势？" | `query_aggregation(active_only=false, group_by="date", date_from="7天前")` | 无 |
| "今天各小时进了多少车？" | `query_aggregation(active_only=false, group_by="hour", date_from="今天", date_to="今天")` | 无 |
| "最近一个月总车次和平均时长？" | `query_aggregation(active_only=false, include_duration=true)` | 无 |
| "工作日vs周末对比？" | `query_aggregation(active_only=false, group_by="day_of_week")` | 无 |
| "京A12345停在哪里？" | `get_vehicle(plate="京A12345")` | 无 |
| "每天各类型车辆占比趋势？" | `sql_query`（二维分组） | 无 |

每个需求只有一条合理路径，不存在"用工具A也行，用工具B也行"的模糊地带。这就是正交性。

---

### 4.5 工具组合解决复杂问题示例

**问题**："对比本月和上月的停车量，生成柱状图"

1. `query_aggregation(active_only=false, date_from="本月1日", date_to="今天")` → 本月总车次
2. `query_aggregation(active_only=false, date_from="上月1日", date_to="上月最后一天")` → 上月总车次
3. LLM 构造对比柱状图的 ECharts option
4. `render_chart(option=...)` → 图表渲染

**问题**："分析各楼层的新能源车占比"

1. `get_config()` → 获取总楼层数
2. `sql_query("SELECT entry_floor, vehicle_type, COUNT(*) FROM vehicle_record WHERE exit_time IS NULL GROUP BY entry_floor, vehicle_type")` → 二维分组
3. LLM 在推理中计算每层的新能源占比

---

## 五、覆盖矩阵：新工具 vs 常见需求

| 需求场景 | get_config | query_aggregation | get_vehicle | render_chart | sql_query |
|----------|:----------:|:-----------------:|:-----------:|:------------:|:---------:|
| 当前空余车位 | | ● `active_only=true` | | | |
| 各类型车辆当前占比 | | ● `group_by="vehicle_type"` | | | |
| 各楼层当前占用 | | ● `group_by="floor"` | | | |
| 每日停车趋势 | | ● `group_by="date"` | | | |
| 时段进出分布 | | ● `group_by="hour"` | | | |
| 月度汇总 | | ● `group_by="month"` | | | |
| 工作日vs周末 | | ● `group_by="day_of_week"` | | | |
| 总车次+平均时长 | | ● `include_duration=true` | | | |
| 车辆个体查询 | | | ● | | |
| 停车场基础信息 | ● | | | | |
| 生成图表 | | | | ● | |
| 二维交叉分组 | | | | | ● |
| 自定义复杂查询 | | | | | ● |

---

## 六、与现有方案对比

| 维度 | 现有方案（9工具） | 新方案（4+1工具） |
|------|------------------|-------------------|
| 工具数量 | 9 | 5（核心4 + 兜底1） |
| 时间范围灵活性 | 仅"当前"或"最近N天" | 任意自定义日期范围 |
| 分组维度 | 5种（隐式分布在6个工具中） | 7种（显式参数） |
| 新增分组维度 | 需新增工具 | 加一个 `group_by` 枚举值 |
| 工作日/周末分析 | 不支持 | `group_by="day_of_week"` |
| 月度趋势 | 不支持 | `group_by="month"` |
| 派生指标 | LLM手动计算 | 工具内置自动计算 |
| 二维交叉分组 | 需 `sql_query` | 需 `sql_query`（同等） |
| 返回结构一致性 | 6种不同格式 | 1种统一格式 |
| LLM认知负担 | 需记忆6个工具的使用场景 | 需理解1个工具的参数组合 |

---

## 七、实施建议

### 7.1 实施路径

**Phase 1**：新增 `query_aggregation` 工具（`backend/tools/aggregation.py`）

- 实现核心 SQL 生成逻辑：根据参数动态构建查询
- 内置派生指标计算（`ratio`、`occupancy_rate`、`vacant`、`rolling_avg_7d`）
- 自动补齐小时数组、自动 JOIN config 表

**Phase 2**：注册新工具到 `TOOL_SCHEMAS` 和 `TOOL_EXECUTORS`

- 新增 `get_config`（从 `parking.py` 提取或新建）
- 新增 `query_aggregation`
- 保留 `get_vehicle`、`render_chart`、`sql_query`

**Phase 3**：更新 `agent.py` 的 SYSTEM_PROMPT

- 描述新工具的用法和典型调用模式
- 引导 LLM 优先使用 `query_aggregation`，仅复杂场景用 `sql_query`

**Phase 4**：移除旧工具（T1-T5, T7）

- 从 `TOOL_SCHEMAS` 和 `TOOL_EXECUTORS` 中移除
- 保留源文件作为参考

### 7.2 `query_aggregation` 实现要点

```python
def query_aggregation(
    active_only: bool = True,
    group_by: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    include_duration: bool = False,
) -> dict:
```

内部逻辑：

1. **参数校验**：`active_only=True` 时忽略 `date_from`/`date_to`/`include_duration` 和无效的 `group_by`
2. **默认值**：`active_only=False` 且未指定 `date_from` 时，默认最近 30 天
3. **SQL 构建**：根据参数动态拼接 `SELECT` / `WHERE` / `GROUP BY` / `ORDER BY`
4. **配置读取**：始终 JOIN `parking_lot_config` 获取 `total_spots`
5. **派生计算**：
   - `ratio = count / total`
   - `vacant = total_spots - occupied`
   - `occupancy_rate = occupied / total_spots`
   - `net_change = entry_count - exit_count`
   - `rolling_avg_7d`（仅 `group_by="date"` 时，使用 pandas 计算）
6. **返回格式化**：统一结构，所有路径返回相同 JSON schema

---

## 八、总结

新工具体系的核心思想是**从场景驱动转向操作原语驱动**：

| 操作原语 | 工具 | 说明 |
|----------|------|------|
| 元数据查询 | `get_config` | 全局配置，独立正交 |
| 聚合统计 | `query_aggregation` | 一个工具 = 原有6个，参数化覆盖所有一维聚合 |
| 个体查询 | `get_vehicle` | 点查，无法被聚合工具替代 |
| 可视化渲染 | `render_chart` | 正交于数据查询层 |
| 灵活兜底 | `sql_query` | 二维分组等边缘需求 |

工具数量从9减至5，覆盖范围扩大（新增 `day_of_week`、`month` 分组、自定义日期范围），功能边界清晰无重叠。LLM 只需理解"一个聚合工具 + 几个参数"的心智模型，即可应对停车场数据的绝大部分分析需求。
