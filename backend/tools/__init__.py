"""Tool registry — collects all tool schemas and implementations."""

from tools.parking import (
    get_current_vacancy, get_nev_ratio, get_trend,
    get_floor_status, get_hourly_distribution, get_vehicle_detail,
    get_summary_stats
)
from tools.sql_tool import sql_query
from tools.chart_tool import render_chart

# Tool schemas in OpenAI function-calling format
TOOL_SCHEMAS = [
    {
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
    },
    {
        "type": "function",
        "function": {
            "name": "get_nev_ratio",
            "description": "查询当前停车场内新能源车的数量和占比",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_hev": {
                        "type": "boolean",
                        "description": "是否将油电混动(HEV)归入新能源车统计，默认False"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_trend",
            "description": "查询最近N天的停车数变化趋势，含每日进出量和峰值占用率",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "查询天数，默认30天，最大120天"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_floor_status",
            "description": "查询各楼层(或指定楼层)的停车位占用情况",
            "parameters": {
                "type": "object",
                "properties": {
                    "floor": {
                        "type": "integer",
                        "description": "楼层号(1-4)，不填则返回所有楼层"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_hourly_distribution",
            "description": "查询某日各小时的车辆进出分布",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {
                        "type": "string",
                        "description": "查询日期，格式YYYY-MM-DD，默认为今天"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_vehicle_detail",
            "description": "按车牌号精确查询车辆的进出记录和当前状态",
            "parameters": {
                "type": "object",
                "properties": {
                    "plate": {
                        "type": "string",
                        "description": "车牌号"
                    }
                },
                "required": ["plate"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_summary_stats",
            "description": "查询最近N天的汇总统计(总车次、平均停车时长、平均占用率等)",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "统计天数，默认7天"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "sql_query",
            "description": "执行受控的只读SQL查询。优先使用预定义函数，仅在预定义函数无法满足需求时使用。支持 SELECT 查询和只读 PRAGMA（如 table_info、index_list、foreign_key_list 等）。写 PRAGMA 会被数据库层自动拦截。",
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
                        "description": "完整的ECharts option对象，必须包含series数组，每个series须有type字段"
                    }
                },
                "required": ["option"]
            }
        }
    },
]

# Tool executor dispatch
TOOL_EXECUTORS = {
    "get_current_vacancy": get_current_vacancy,
    "get_nev_ratio": get_nev_ratio,
    "get_trend": get_trend,
    "get_floor_status": get_floor_status,
    "get_hourly_distribution": get_hourly_distribution,
    "get_vehicle_detail": get_vehicle_detail,
    "get_summary_stats": get_summary_stats,
    "sql_query": sql_query,
    "render_chart": render_chart,
}
