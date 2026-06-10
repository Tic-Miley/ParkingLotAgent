"""
ReAct Agent 循环。

协调 LLM (DeepSeek V4) 与工具执行，产生 SSE 流式响应。
"""

import json
import datetime
from typing import Any

from openai import AsyncOpenAI

import config
from tools import TOOL_SCHEMAS, TOOL_EXECUTORS
from sse import SSESender

SYSTEM_PROMPT = """你是一个停车场数据分析助手，基于 DeepSeek V4 运行。你拥有以下工具：

## 工具清单

1. **get_config** — 获取停车场全局配置（总车位数、楼层数、费率）
2. **query_aggregation** — 核心聚合查询工具，一个工具覆盖绝大多数分析场景
3. **get_vehicle** — 按车牌号查询车辆详情
4. **sql_query** — 受控只读 SQL（兜底工具，仅在 query_aggregation 无法覆盖时使用）
5. **render_chart** — 生成 ECharts 图表（饼图/折线图/柱状图）

## query_aggregation 使用指南（核心工具）

这是你最重要的工具。通过参数组合覆盖几乎所有查询场景：

| 用户问题 | 调用方式 |
|----------|----------|
| "还有多少车位？" | `query_aggregation(active_only=true)` → 取 `vacant` |
| "各类型车辆占比？" | `query_aggregation(active_only=true, group_by="vehicle_type")` |
| "各楼层还有位吗？" | `query_aggregation(active_only=true, group_by="floor")` |
| "最近一周每日停车趋势？" | `query_aggregation(active_only=false, group_by="date", date_from="7天前")` |
| "今天各小时进出分布？" | `query_aggregation(active_only=false, group_by="hour", date_from="今天", date_to="今天")` |
| "最近30天总车次和平均时长？" | `query_aggregation(active_only=false, include_duration=true)` |
| "工作日vs周末对比？" | `query_aggregation(active_only=false, group_by="day_of_week")` |
| "月度趋势？" | `query_aggregation(active_only=false, group_by="month")` |

参数说明：
- `active_only`: true=当前在场车辆快照, false=历史记录
- `group_by`: null/vehicle_type/floor/date/hour/day_of_week/month
- `date_from` / `date_to`: YYYY-MM-DD 格式，仅 active_only=false 时有效
- `include_duration`: 是否附带平均停车时长

**重要**：active_only=true 时 group_by 只能选 null、"vehicle_type"、"floor" 三种！

## 工具选择优先级

1. 优先用 `query_aggregation` — 覆盖 90% 的查询场景
2. 车辆个体查询用 `get_vehicle`
3. 需要总车位数/楼层数等上下文时先调用 `get_config`
4. 仅在二维交叉分组（如"每天各类型的占比趋势"）等 query_aggregation 无法覆盖时，才用 `sql_query`
5. 数据就绪后用 `render_chart` 生成图表

## 工作原则

- 使用工具获取数据，不要编造数字
- 回答简洁专业，先给结论再给细节
- 当数据适合可视化时，调用 render_chart
- 饼图用于占比，折线图用于趋势，柱状图用于对比
- 图表配色由前端主题自动管理，无需在 option 中指定 color

## 数据说明

- 停车场配置通过 get_config 获取（默认 800 车位、4 层）
- 新能源车：BEV=纯电动, PHEV=插电混动, HEV=油电混动
- 车辆类型代码：ICE=燃油车, BEV=纯电动, PHEV=插电混动, HEV=油电混动
- 当前时间：{current_datetime}

## 图表生成规范

生成 ECharts option 时遵循：
- title.text 简洁明了
- 饼图使用 radius: "60%" 环形样式
- 折线图使用 smooth: true 平滑曲线
- tooltip 始终包含
- 不需要 legend（数据类别少）

## 对话示例

用户：现在还剩多少车位？
助手：[调用 query_aggregation(active_only=true)]
查询结果：总车位800个，已占用523个，剩余**277个**车位，占用率65.4%。
[调用 render_chart 生成占用饼图]

用户：最近一周停车趋势如何？
助手：[调用 query_aggregation(active_only=false, group_by="date", date_from="2026-06-03", date_to="2026-06-10")]
从趋势看，本周日均停车约1450车次，峰值占用率75%。周三最高，周末略有下降。
[调用 render_chart 生成折线图]

用户：工作日和周末停车量有区别吗？
助手：[调用 query_aggregation(active_only=false, group_by="day_of_week", date_from="2026-05-01")]
工作日日均1500车次，周末日均1050车次，周末比工作日少约30%。
"""


def _get_client() -> AsyncOpenAI:
    """Create DeepSeek-compatible async OpenAI client."""
    return AsyncOpenAI(
        api_key=config.DEEPSEEK_API_KEY,
        base_url=config.DEEPSEEK_BASE_URL,
        timeout=60.0,
    )


async def execute_tool(tool_name: str, arguments: dict[str, Any]) -> dict:
    """Execute a single tool and return its result."""
    executor = TOOL_EXECUTORS.get(tool_name)
    if not executor:
        return {"error": f"未知工具: {tool_name}"}

    try:
        result = executor(**arguments) if arguments else executor()
        return result if isinstance(result, dict) else {"result": result}
    except TypeError as e:
        return {"error": f"工具参数错误: {str(e)}。请检查参数名称和类型。"}
    except Exception as e:
        return {"error": f"工具执行失败: {str(e)}"}


async def agent_loop(
    user_message: str,
    history: list[dict] | None = None,
    send_sse: SSESender | None = None,
) -> str:
    """
    执行 ReAct Agent 循环。

    Args:
        user_message: 用户的输入消息
        history: 之前的对话历史
        send_sse: SSE 事件发送器（None 表示非流式模式）

    Returns:
        助手完整回复文本
    """
    client = _get_client()

    # 构建消息
    now_str = datetime.datetime.now().strftime("%Y年%m月%d日 %H:%M")
    system_content = SYSTEM_PROMPT.replace("{current_datetime}", now_str)

    messages: list[Any] = [{"role": "system", "content": system_content}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    for _ in range(config.MAX_ITERATIONS):
        # 工具决策阶段（非流式）
        response = await client.chat.completions.create(  # type: ignore[reportArgumentType]
            model=config.DEEPSEEK_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,  # type: ignore[reportArgumentType]
            tool_choice="auto",
            stream=False,
            extra_body={"thinking": {"type": config.THINKING_MODE}},
        )

        assistant_msg = response.choices[0].message

        if assistant_msg.tool_calls:
            # 工具调用阶段
            messages.append(assistant_msg)

            for tool_call in assistant_msg.tool_calls:
                tool_name = tool_call.function.name
                try:
                    arguments = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    arguments = {}

                # 通知前端：工具开始执行
                if send_sse:
                    await send_sse.tool_call(
                        tool_name=tool_name,
                        status="running",
                        arguments=arguments,
                        message=f"正在查询{tool_name}...",
                    )

                # 执行工具
                result = await execute_tool(tool_name, arguments)

                # 通知前端：工具执行完成
                if send_sse:
                    if "error" in result:
                        await send_sse.tool_call(
                            tool_name=tool_name,
                            status="error",
                            error=result["error"],
                        )
                    else:
                        # 截断长结果用于预览
                        preview = _truncate_preview(result)
                        await send_sse.tool_call(
                            tool_name=tool_name,
                            status="done",
                            result_preview=preview,
                        )

                        # 如果是 render_chart 且成功，推送 chart 事件
                        if tool_name == "render_chart" and result.get("status") == "rendered":
                            await send_sse.chart(
                                chart_id=result["chart_id"],
                                chart_type=result["chart_type"],
                                option=result["option"],
                            )

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result, ensure_ascii=False),
                })

        else:
            # 文本响应阶段：流式输出
            stream = await client.chat.completions.create(  # type: ignore[reportArgumentType]
                model=config.DEEPSEEK_MODEL,
                messages=messages,
                stream=True,
                extra_body={"thinking": {"type": config.THINKING_MODE}},
            )

            full_response = ""
            async for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    token = chunk.choices[0].delta.content
                    full_response += token
                    if send_sse:
                        await send_sse.text(token)

            messages.append({
                "role": "assistant",
                "content": full_response,
            })

            if send_sse:
                try:
                    usage = {
                        "prompt_tokens": response.usage.prompt_tokens if response.usage else 0,
                        "completion_tokens": response.usage.completion_tokens if response.usage else 0,
                        "total_tokens": response.usage.total_tokens if response.usage else 0,
                    }
                except Exception:
                    usage = None
                await send_sse.done(usage=usage)

            return full_response

    # 超过最大迭代次数
    error_msg = "抱歉，我暂时无法完成这个查询。请尝试换个方式提问。"
    if send_sse:
        await send_sse.text(error_msg)
        await send_sse.done(status="error")
    return error_msg


def _truncate_preview(result: dict, max_chars: int = 200) -> dict:
    """截断长结果用于 SSE 预览。"""
    s = json.dumps(result, ensure_ascii=False)
    if len(s) <= max_chars:
        return result
    # 对 trend 等大数组做摘要
    preview = dict(result)
    for key in list(preview.keys()):
        val = preview[key]
        if isinstance(val, list) and len(val) > 5:
            preview[key] = f"[{len(val)} items]"
        elif isinstance(val, dict):
            # 嵌套对象也尝试截断
            for sub_key in list(val.keys()):
                if isinstance(val[sub_key], list) and len(val[sub_key]) > 5:
                    val[sub_key] = f"[{len(val[sub_key])} items]"
    return preview