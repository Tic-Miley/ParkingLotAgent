"""Tool registry v2 — 5 tools (4 core + 1 fallback).

v2 变更 (2026-06-10):
- 从 9 工具精简为 5 工具
- 新增 get_config: 停车场全局配置
- 新增 query_aggregation: 通用参数化聚合 (替代 T1-T5, T7)
- get_vehicle_detail 重命名为 get_vehicle
- 保留 sql_query (T8) 和 render_chart (T9)
"""

from tools.parking import get_config, get_vehicle
from tools.aggregation import query_aggregation
from tools.sql_tool import sql_query
from tools.chart_tool import render_chart

# ── Tool Schemas (OpenAI function-calling format) ─────────

TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "get_config",
            "description": "获取停车场全局配置（总车位数、楼层数、每层车位数、费率等）",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "query_aggregation",
            "description": (
                "通用聚合查询工具 —— 一个工具覆盖几乎所有停车场数据分析场景。\n"
                "通过参数组合实现：当前空余车位、车辆类型分布、楼层占用、每日趋势、"
                "时段分布、星期几分布、月度汇总、平均停车时长等。\n"
                "优先使用本工具，仅在需要二维交叉分组等本工具无法覆盖的场景时才用 sql_query。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "active_only": {
                        "type": "boolean",
                        "description": (
                            "true=仅查询当前在场车辆（快照），false=查询历史记录。"
                            "默认为 true。设为 false 时才能使用 date_from/date_to/include_duration。"
                        ),
                    },
                    "group_by": {
                        "type": "string",
                        "enum": [
                            None,
                            "vehicle_type",
                            "floor",
                            "date",
                            "hour",
                            "day_of_week",
                            "month",
                        ],
                        "description": (
                            "分组维度：null=全局聚合, vehicle_type=按能源类型, "
                            "floor=按楼层, date=按日, hour=按小时, "
                            "day_of_week=按星期几, month=按月。"
                            "active_only=true 时仅支持 null/vehicle_type/floor。"
                        ),
                    },
                    "date_from": {
                        "type": "string",
                        "description": (
                            "起始日期 YYYY-MM-DD。仅 active_only=false 时有效，"
                            "默认为 30 天前。"
                        ),
                    },
                    "date_to": {
                        "type": "string",
                        "description": (
                            "结束日期 YYYY-MM-DD。仅 active_only=false 时有效，"
                            "默认为今天。"
                        ),
                    },
                    "include_duration": {
                        "type": "boolean",
                        "description": (
                            "是否附带平均停车时长（分钟）。仅 active_only=false 时有效。"
                        ),
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_vehicle",
            "description": "按车牌号精确查询车辆的进出记录、当前状态和历史访问次数",
            "parameters": {
                "type": "object",
                "properties": {
                    "plate": {
                        "type": "string",
                        "description": "车牌号，如 京A12345",
                    },
                },
                "required": ["plate"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "sql_query",
            "description": (
                "执行受控的只读SQL查询。优先使用 query_aggregation 等预定义工具，"
                "仅在预定义工具无法满足需求时使用（如二维交叉分组）。"
                "支持 SELECT 查询和只读 PRAGMA。"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "只读 SELECT SQL 查询语句",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "render_chart",
            "description": "根据数据生成ECharts图表。支持饼图(pie)、折线图(line)、柱状图(bar)。传入完整的ECharts option JSON。",
            "parameters": {
                "type": "object",
                "properties": {
                    "option": {
                        "type": "object",
                        "description": "完整的ECharts option对象，必须包含series数组，每个series须有type字段",
                    },
                },
                "required": ["option"],
            },
        },
    },
]

# ── Tool Executor Dispatch ───────────────────────────────

TOOL_EXECUTORS = {
    "get_config": get_config,
    "query_aggregation": query_aggregation,
    "get_vehicle": get_vehicle,
    "sql_query": sql_query,
    "render_chart": render_chart,
}
