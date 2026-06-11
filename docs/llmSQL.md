# LLM 生成 SQL 的优化方案

> 版本 1.0 | 2026-06-09 | 结合 ParkingLotDS 现有代码分析

---

## 一、问题域

当预定义工具（`query_aggregation` / `get_vehicle` / `get_config`）无法满足需求时，LLM 需要降级到 `sql_query` 自行编写 SQL。这引入两个核心问题：

1. **降级判断**：LLM 如何判断"该降级了"？何时用预定义工具，何时写 SQL？
2. **SQL 验证**：LLM 生成的 SQL 如何保证安全性和正确性？需要哪些验证机制？

---

## 二、降级判断

### 2.1 `query_aggregation` 的能力边界

`query_aggregation` 的核心能力是**一维聚合**——按单一维度 `GROUP BY` + `COUNT`/`AVG`。降级发生在查询需要跨越这个边界时。

### 2.2 降级触发条件

| # | 触发条件 | 典型用户问题 | SQL 特征 |
|---|---------|-------------|---------|
| 1 | **二维交叉分组** | "每天各类型车辆占比趋势" | `GROUP BY date, vehicle_type` |
| 2 | **自定义 WHERE 过滤** | "停车超过3小时的BEV有多少" | `WHERE (julianday(...)-julianday(...))*24*60 > 180 AND vehicle_type='BEV'` |
| 3 | **子查询/嵌套** | "比平均时长更长的车辆" | `WHERE duration > (SELECT AVG(...))` |
| 4 | **排序 + LIMIT** | "占用率最高的3天" | `ORDER BY ... DESC LIMIT 3` |
| 5 | **HAVING 过滤** | "日停车量超过1500的天数" | `HAVING COUNT(*) > 1500` |
| 6 | **窗口函数** | "每辆车第几次来停车场" | `ROW_NUMBER() OVER (PARTITION BY plate ORDER BY entry_time)` |

### 2.3 不需要降级的情况（LLM 常误判）

| 场景 | 错误做法 | 正确做法 |
|------|---------|---------|
| "各楼层占用率" | `sql_query` 手动 JOIN config | `query_aggregation(active_only=true, group_by="floor")` — 工具已内置 JOIN 并返回 `occupancy_rate` |
| "当前总占用率" | `sql_query` 手动算 | `query_aggregation(active_only=true)` — 工具已返回 `vacant`、`occupancy_rate` |
| "新能源车中 BEV 占多少" | `sql_query` 过滤 | `query_aggregation(active_only=true, group_by="vehicle_type")` → LLM 自行从 breakdown 中算 `BEV/total` |

### 2.4 决策树

```
用户请求
│
├─ 目标是一辆车？                              → get_vehicle(plate)
├─ 目标是停车场元数据？                         → get_config()
│
├─ 需要聚合统计？
│  │
│  ├─ 按【单个维度】分组？
│  │  ├─ 在场车辆 + (类型/楼层/全局)            → query_aggregation(active_only=true, group_by=...)
│  │  └─ 历史数据 + (日期/小时/星期/月/类型/楼层) → query_aggregation(active_only=false, group_by=..., date_from=..., date_to=...)
│  │
│  ├─ 按【两个维度】交叉分组？                   → sql_query
│  ├─ 需【子查询/窗口函数/HAVING】？             → sql_query
│  └─ 需【排序+限制/自定义WHERE】？              → sql_query
│
└─ 需要图表？                                   → render_chart(option)
```

**关键判断口诀**：`GROUP BY` 后面只有一个字段 → `query_aggregation`；`GROUP BY` 后面有两个字段或查询包含子查询/窗口函数/HAVING → `sql_query`。

### 2.5 在 SYSTEM_PROMPT 中落地

```markdown
## 工具选择规则

1. 查一辆车 → get_vehicle
2. 按单一维度统计（在场/历史） → query_aggregation
3. 需要交叉两个维度、子查询、窗口函数、HAVING、自定义WHERE、ORDER BY LIMIT → sql_query
4. 生成图表 → render_chart

核心判断：如果需要 GROUP BY 后面有两个字段，或者需要子查询/窗口函数/HAVING，必须用 sql_query。
query_aggregation 内部已 JOIN config 表并自动计算了占用率、空余车位等，不需要为这些指标手动写 SQL。
```

---

## 三、SQL 验证：多层防线分析

### 3.1 现有四层防线

```
SQL 文本
  │
  ├─ 第1层：关键字黑名单（sql_tool.py L13-17）
  │   DROP/DELETE/UPDATE/INSERT/ALTER/CREATE/ATTACH/DETACH/VACUUM
  │   → 正则匹配，拦截破坏性操作关键词
  │
  ├─ 第2层：语句类型白名单（sql_tool.py L36-37）
  │   仅允许 SELECT 和 PRAGMA
  │   → 拦截所有非查询语句
  │
  ├─ 第3层：SQLite 内核级只读（db.py L38-39 + sql_tool.py L52）
  │   URI mode=ro + PRAGMA query_only=ON
  │   → 即使黑名单被绕过，内核层也拒绝任何写操作
  │
  └─ 第4层：资源限制（sql_tool.py L20, L59）
      1000行上限 + 5秒查询超时
      → 防止查询耗尽内存或返回海量数据
```

### 3.2 防线评估

| 防线 | 强度 | 覆盖的攻击面 | 盲区 |
|------|:----:|------------|------|
| 关键字黑名单 | 中 | 明显恶意注入 | 可被编码绕过，但第3层兜底 |
| 类型白名单 | 高 | 非查询语句 | SELECT 和 PRAGMA 已覆盖所有合法需求 |
| 内核只读 | **极高** | 所有写操作 | 无——SQLite 内核级拦截，不可绕过 |
| 资源限制 | 高 | DoS、数据泄露 | 无 |

### 3.3 `EXPLAIN QUERY PLAN` 是否需要？

| 考量维度 | 分析 | 结论 |
|---------|------|------|
| 数据量 | 18万行，SQLite 全表扫描仍在 50-100ms 级别 | 性能不是瓶颈 |
| 索引覆盖 | 5个索引已覆盖所有常见查询路径 | 索引缺失概率极低 |
| 延迟成本 | 每次 `sql_query` 多一次 EXPLAIN 往返（~30ms） | 用户体验有感知影响 |
| 实际收益 | EXPLAIN 只能发现"未使用索引"，不能阻止执行 | 收益极低 |
| 替代方案 | 5秒超时 + 1000行上限已有效限制慢查询影响 | 已有替代防线 |

**结论：不需要 EXPLAIN 验证。** 现有四层防线已经形成可靠的纵深防御。真正的优化方向不是运行时检查 SQL 执行计划，而是**让 LLM 写出正确的 SQL**——通过增强 Schema 可见性来预防错误。

---

## 四、Schema 可见性优化

### 4.1 问题诊断

LLM 编写 SQL 最常犯的错误是**字段名错误**（`no such column`）。根源在于 LLM 不知道准确的表结构和字段名。现有体系中，这些信息仅散落在 `agent.py` 的 SYSTEM_PROMPT 中（L35-39），而 `sql_query` 的工具描述中完全没有 schema 信息。

### 4.2 优化：在 `sql_query` 工具描述中嵌入 Schema

将关键 schema 信息直接写入 `sql_query` 的 `description` 字段，LLM 在决定调用该工具时就能看到：

```python
{
    "type": "function",
    "function": {
        "name": "sql_query",
        "description": (
            "执行受控的只读SQL查询。仅当 query_aggregation 无法满足需求时使用。\n\n"
            "## 典型降级场景\n"
            "- 二维交叉分组: GROUP BY a, b\n"
            "- 子查询: WHERE x > (SELECT AVG(...))\n"
            "- 窗口函数: ROW_NUMBER() OVER (...)\n"
            "- HAVING 过滤: HAVING COUNT(*) > N\n"
            "- 自定义 ORDER BY LIMIT\n\n"
            "## 数据库Schema\n"
            "parking_lot_config(id, name, total_spots, floors, spots_per_floor, hourly_rate)\n"
            "vehicle_record(\n"
            "  id, plate, vehicle_type, entry_time, exit_time, entry_floor, entry_spot\n"
            ")\n"
            "  - vehicle_type 取值: 'ICE','BEV','PHEV','HEV'\n"
            "  - exit_time IS NULL = 车辆在场\n\n"
            "## 可用索引\n"
            "idx_entry_time(entry_time), idx_exit_time(exit_time),\n"
            "idx_vehicle_type(vehicle_type), idx_plate(plate),\n"
            "idx_active(entry_time WHERE exit_time IS NULL)\n\n"
            "## 正确SQL示例\n"
            "1. 二维分组: SELECT DATE(entry_time) as dt, vehicle_type, COUNT(*) \n"
            "   FROM vehicle_record \n"
            "   WHERE entry_time >= '2026-05-01' \n"
            "   GROUP BY dt, vehicle_type ORDER BY dt\n\n"
            "2. 子查询+过滤: SELECT * FROM vehicle_record \n"
            "   WHERE exit_time IS NOT NULL \n"
            "   AND (julianday(exit_time)-julianday(entry_time))*24*60 > 180\n\n"
            "3. HAVING: SELECT DATE(entry_time) as dt, COUNT(*) as cnt \n"
            "   FROM vehicle_record \n"
            "   GROUP BY dt HAVING cnt > 1500\n\n"
            "## 安全限制\n"
            "只读模式、最多返回1000行、超时5秒"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "只读SELECT SQL查询语句"
                }
            },
            "required": ["query"]
        }
    }
}
```

**预期效果**：LLM 看到这段描述后，字段名错误率大幅下降。

---

## 五、错误恢复优化

### 5.1 现有错误返回

```python
# sql_tool.py L75
return {"error": f"查询执行失败: {str(e)}"}
```

LLM 收到 `"查询执行失败: no such column: foo"` 后，需要猜测哪个字段拼错了。

### 5.2 优化：结构化错误 + Schema 提示

```python
SCHEMA_HINT = (
    "可用表及字段:\n"
    "- parking_lot_config: id, name, total_spots, floors, spots_per_floor, hourly_rate\n"
    "- vehicle_record: id, plate, vehicle_type(ICE/BEV/PHEV/HEV), "
    "entry_time, exit_time(NULL=在场), entry_floor, entry_spot\n"
    "可用索引: idx_entry_time, idx_exit_time, idx_vehicle_type, idx_plate, idx_active"
)

def sql_query(query: str) -> dict:
    ...
    except Exception as e:
        error_msg = str(e)
        hint = None
        if "no such" in error_msg.lower():
            hint = SCHEMA_HINT
        elif "syntax error" in error_msg.lower():
            hint = "请检查SQL语法: 确保关键字拼写正确、括号匹配、字符串用单引号"
        elif "ambiguous column" in error_msg.lower():
            hint = "列名在多个表中存在，请使用 table.column 格式明确指定"

        return {
            "error": "SQL执行失败",
            "detail": error_msg,
            **({"hint": hint} if hint else {}),
            "query": query
        }
```

**效果对比**：

|  | 现有返回 | 优化后返回 |
|------|---------|----------|
| 内容 | `"查询执行失败: no such column: foo"` | `{"error": "SQL执行失败", "detail": "no such column: foo", "hint": "可用字段: plate, vehicle_type...", "query": "SELECT foo FROM..."}` |
| LLM 恢复 | 需额外推理 → 可能猜错 → 多轮迭代 | 看到 hint → 直接修正 → 下一轮成功 |

### 5.3 不需要在 Agent 循环中增加重试逻辑

现有 `agent.py` 的 ReAct 循环已支持多轮迭代（`MAX_ITERATIONS=8`）。当 `sql_query` 返回 error 时，LLM 在下一轮迭代中看到错误信息，会自动修正 SQL 后重试。单次工具失败不需要特殊处理——这是 ReAct 模式的标准行为。

---

## 六、防线全景图

```
┌──────────────────────────────────────────────────────────┐
│                    预防层（LLM 侧）                        │
│                                                          │
│  ┌─────────────────────┐  ┌────────────────────────────┐ │
│  │ SYSTEM_PROMPT       │  │ sql_query description      │ │
│  │ · 工具选择决策树     │  │ · Schema 速查（表名+字段）   │ │
│  │ · 降级触发条件       │  │ · 索引列表                  │ │
│  │ · 典型场景映射       │  │ · 正确SQL示例               │ │
│  └─────────────────────┘  └────────────────────────────┘ │
│                         ↓                                │
│               LLM 生成 SQL（正确率↑）                      │
└──────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                    执行层（运行时）                         │
│                                                          │
│  第1层: 关键字黑名单  ──→  第2层: 类型白名单               │
│  (DROP/DELETE/UPDATE...)    (仅允许 SELECT/PRAGMA)        │
│         │                          │                     │
│         └──────────┬───────────────┘                     │
│                    ▼                                      │
│  第3层: SQLite 内核只读  ──→  第4层: 资源限制              │
│  (mode=ro + query_only=ON)    (1000行 + 5秒超时)          │
│                                                          │
│  → 安全执行或返回错误                                     │
└──────────────────────────────────────────────────────────┘
                           │
                           ▼
┌──────────────────────────────────────────────────────────┐
│                    恢复层（错误反馈）                       │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │ 结构化错误返回                                      │ │
│  │ · error: 错误类型                                   │ │
│  │ · detail: 原始错误信息                               │ │
│  │ · hint: Schema 提示（no such column时）              │ │
│  │ · query: 原始查询（供 LLM 参考修正）                  │ │
│  └────────────────────────────────────────────────────┘ │
│                         ↓                                │
│         LLM 下一轮迭代自动修正 → 重试成功                   │
└──────────────────────────────────────────────────────────┘
```

---

## 七、实施清单

| # | 优化项 | 文件 | 优先级 | 工作量 |
|---|--------|------|:------:|:------:|
| 1 | `sql_query` 描述嵌入 Schema + 示例 + 降级场景 | `backend/tools/__init__.py` | **高** | 1处修改 |
| 2 | `query_aggregation` 描述明确能力边界 | `backend/tools/__init__.py` | **高** | 1处修改 |
| 3 | SYSTEM_PROMPT 增加工具选择规则 | `backend/agent.py` | **高** | 追加段落 |
| 4 | `sql_query` 错误返回结构化 + hint | `backend/tools/sql_tool.py` | **中** | 1处修改 |
| 5 | `EXPLAIN QUERY PLAN` | — | **不做** | — |

---

## 八、总结

LLM 生成 SQL 的优化遵循"预防优于检测，检测优于恢复"的原则：

| 策略 | 手段 | 解决的问题 |
|------|------|----------|
| **预防** | Schema 嵌入工具描述 + SYSTEM_PROMPT 决策树 | 减少错误 SQL 的产生 |
| **检测** | 4层运行时防线（黑名单→白名单→只读→限制） | 防止破坏性操作和资源耗尽 |
| **恢复** | 结构化错误 + Schema hint | LLM 自动修正错误 SQL |

不需要 `EXPLAIN`——18 万行数据量级下 SQLite 性能不是瓶颈，且 4 层防线已足够。真正的投入应该在**让 LLM 在写 SQL 之前就看到 Schema**，而非在运行时检查执行计划。
