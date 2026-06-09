"""
ReAct Agent 循环。

协调 LLM (DeepSeek V4) 与工具执行，产生 SSE 流式响应。
"""

import json
import time
import datetime
from typing import Any

from openai import AsyncOpenAI

import config
from tools import TOOL_SCHEMAS, TOOL_EXECUTORS
from sse import SSESender

SYSTEM_PROMPT = """你是一个停车场数据分析助手。你拥有以下能力：

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
- 图表配色由前端主题系统自动管理，无需在 option 中指定 color 字段
- tooltip 始终包含
- 不需要 legend（数据类别少）

## 错误处理

- 如果工具返回错误，如实告知用户并建议替代方案
- 如果数据不足（如查询时间范围超出数据覆盖范围），说明可用数据范围

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

    messages = [{"role": "system", "content": system_content}]
    if history:
        messages.extend(history)
    messages.append({"role": "user", "content": user_message})

    for iteration in range(config.MAX_ITERATIONS):
        # 工具决策阶段（非流式）
        response = await client.chat.completions.create(
            model=config.DEEPSEEK_MODEL,
            messages=messages,
            tools=TOOL_SCHEMAS,
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
            stream = await client.chat.completions.create(
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
