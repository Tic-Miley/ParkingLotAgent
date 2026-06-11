# 停车场管理系统 — 数据库结构

> 数据库引擎：SQLite3  
> 数据库文件：`data/parking_lot.db`  
> 字符集：UTF-8  
> 启用 WAL 模式 + 外键约束  

---

## 表清单

| 表名 | 说明 | 主键 | 行数估计 |
|------|------|------|----------|
| `parking_lot_config` | 停车场全局配置（单行） | `id` (固定为 1) | 1 |
| `vehicle_record` | 车辆停放记录（核心业务表） | `id` (自增) | ~180,000（120 天生成） |

---

## 1. `parking_lot_config` — 停车场配置表

存放停车场的基础参数，仅保留 **一行** 记录（`id = 1`），通过 `INSERT OR IGNORE` 初始化。

| 字段 | 类型 | 约束 | 默认值 | 说明 |
|------|------|------|--------|------|
| `id` | `INTEGER` | `PRIMARY KEY CHECK (id = 1)` | — | 单行标识，固定为 1 |
| `name` | `TEXT` | `NOT NULL` | `'Demo停车场'` | 停车场名称 |
| `total_spots` | `INTEGER` | `NOT NULL` | `800` | 总车位数 |
| `floors` | `INTEGER` | `NOT NULL` | `4` | 楼层数 |
| `spots_per_floor` | `INTEGER` | `NOT NULL` | `200` | 每层车位数 |
| `hourly_rate` | `REAL` | `NOT NULL` | `6.0` | 每小时停车费率（元） |
| `created_at` | `DATETIME` | — | `CURRENT_TIMESTAMP` | 记录创建时间 |

**SQL 定义：**

```sql
CREATE TABLE IF NOT EXISTS parking_lot_config (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    name TEXT NOT NULL DEFAULT 'Demo停车场',
    total_spots INTEGER NOT NULL DEFAULT 800,
    floors INTEGER NOT NULL DEFAULT 4,
    spots_per_floor INTEGER NOT NULL DEFAULT 200,
    hourly_rate REAL NOT NULL DEFAULT 6.0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**示例数据：**

| id | name | total_spots | floors | spots_per_floor | hourly_rate | created_at |
|----|------|-------------|--------|-----------------|-------------|------------|
| 1 | Demo停车场 | 800 | 4 | 200 | 6.0 | 2026-06-09 10:00:00 |

---

## 2. `vehicle_record` — 车辆停放记录表

核心业务表，记录每一辆车的进出场信息。由 `data_generator.py` 按容量感知时间线模拟生成 120 天历史数据。

| 字段 | 类型 | 约束 | 说明 |
|------|------|------|------|
| `id` | `INTEGER` | `PRIMARY KEY AUTOINCREMENT` | 自增记录 ID |
| `plate` | `TEXT` | `NOT NULL` | 车牌号（模拟格式：`京A00001`） |
| `vehicle_type` | `TEXT` | `NOT NULL CHECK(IN ('ICE','BEV','PHEV','HEV'))` | 车辆能源类型 |
| `entry_time` | `DATETIME` | `NOT NULL` | 入场时间（精确到秒） |
| `exit_time` | `DATETIME` | 可空 | 离场时间；`NULL` 表示至今未离场 |
| `entry_floor` | `INTEGER` | `CHECK(1–10)` | 入场楼层（1–4） |
| `entry_spot` | `INTEGER` | 无 | 入场车位号（1–200） |

### 车辆类型枚举

| 代码 | 全称 | 说明 | 生成权重 |
|------|------|------|:--------:|
| `ICE` | Internal Combustion Engine | 传统燃油车 | 55% |
| `BEV` | Battery Electric Vehicle | 纯电动车 | 25% |
| `PHEV` | Plug-in Hybrid Electric Vehicle | 插电混动车 | 12% |
| `HEV` | Hybrid Electric Vehicle | 非插电混动车 | 8% |

### 关键业务规则

- **容量感知**：任意时间断面 `COUNT(在场车辆) ≤ total_spots (800)`，模拟时满场则跳过后续到达。
- **在场判断**：`entry_time ≤ 目标时刻 AND (exit_time IS NULL OR exit_time > 目标时刻)`。
- **离场时间 NULL**：`exit_time = NULL` 表示车辆至今仍在场（停留超过当前系统时间）。
- **数据覆盖**：过去 120 天，含早晚高峰、周末模式，约 18 万条记录。

**SQL 定义：**

```sql
CREATE TABLE IF NOT EXISTS vehicle_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    plate TEXT NOT NULL,
    vehicle_type TEXT NOT NULL
        CHECK(vehicle_type IN ('ICE', 'BEV', 'PHEV', 'HEV')),
    entry_time DATETIME NOT NULL,
    exit_time DATETIME,
    entry_floor INTEGER CHECK(entry_floor BETWEEN 1 AND 10),
    entry_spot INTEGER
);
```

---

## 3. 索引

所有索引建立在 `vehicle_record` 表上，优化常见查询路径。

| 索引名 | 字段 | 类型 | 用途 |
|--------|------|------|------|
| `idx_entry_time` | `entry_time` | 普通 B-Tree | 按入场时间范围查询 |
| `idx_exit_time` | `exit_time` | 普通 B-Tree | 按离场时间范围查询 |
| `idx_vehicle_type` | `vehicle_type` | 普通 B-Tree | 按能源类型过滤/分组 |
| `idx_plate` | `plate` | 普通 B-Tree | 按车牌精确查找 |
| `idx_active` | `entry_time` | **部分索引** `WHERE exit_time IS NULL` | 快速统计/查询在场车辆 |

```sql
CREATE INDEX IF NOT EXISTS idx_entry_time    ON vehicle_record(entry_time);
CREATE INDEX IF NOT EXISTS idx_exit_time     ON vehicle_record(exit_time);
CREATE INDEX IF NOT EXISTS idx_vehicle_type  ON vehicle_record(vehicle_type);
CREATE INDEX IF NOT EXISTS idx_plate         ON vehicle_record(plate);
CREATE INDEX IF NOT EXISTS idx_active        ON vehicle_record(entry_time)
    WHERE exit_time IS NULL;
```

> `idx_active` 是**部分索引（Partial Index）**，仅覆盖 `exit_time IS NULL` 的行。  
> 查询在场车辆时 SQLite 可直接扫描该索引，无需全表过滤。

---

## 4. 实体关系图（简要）

```
┌──────────────────────────┐
│   parking_lot_config     │
│──────────────────────────│
│ id          PK (固定=1)  │
│ name                     │
│ total_spots              │
│ floors                   │
│ spots_per_floor          │
│ hourly_rate              │
│ created_at               │
└──────────────────────────┘
            │
            │ 1 : N (逻辑关联，无外键约束)
            ▼
┌──────────────────────────┐
│    vehicle_record        │
│──────────────────────────│
│ id          PK AUTOINC   │
│ plate                    │
│ vehicle_type  CHECK(...) │
│ entry_time               │
│ exit_time    (NULL=在场)  │
│ entry_floor              │
│ entry_spot               │
└──────────────────────────┘
```

- 两表之间**无显式外键约束**，通过 `entry_floor` / `entry_spot` 与配置表的 `floors` / `spots_per_floor` 形成逻辑关联。
- `parking_lot_config` 为**全局单例配置**，`vehicle_record` 为**时序事件记录**。

---

## 5. 常用查询示例

### 查询当前在场车辆

```sql
SELECT *
FROM vehicle_record
WHERE exit_time IS NULL
ORDER BY entry_time DESC;
```

### 统计各能源类型在场车辆数

```sql
SELECT vehicle_type, COUNT(*) AS cnt
FROM vehicle_record
WHERE exit_time IS NULL
GROUP BY vehicle_type;
```

### 查询某天进场总量

```sql
SELECT COUNT(*)
FROM vehicle_record
WHERE entry_time >= '2026-02-09 00:00:00'
  AND entry_time <  '2026-02-10 00:00:00';
```

### 按小时统计平均进场量（含在场峰值）

```sql
SELECT
    STRFTIME('%H', entry_time) AS hour,
    COUNT(*) AS arrivals,
    AVG(CAST((JULIANDAY(exit_time) - JULIANDAY(entry_time)) * 24 AS REAL)) AS avg_duration_h
FROM vehicle_record
WHERE exit_time IS NOT NULL
GROUP BY hour
ORDER BY hour;
```
