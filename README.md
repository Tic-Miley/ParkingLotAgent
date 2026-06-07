# 🅿️ 停车场 AI Agent 仿真演示系统

基于 DeepSeek V4 的停车场数据分析对话系统。AI Agent 理解自然语言问题，自动选择合适的工具查询 SQLite 数据库，并生成文本回答 + 统计图表。

## 技术栈

| 层 | 技术 |
|----|------|
| LLM | DeepSeek V4 (OpenAI 兼容 API) |
| Agent | 手写 ReAct Loop (Python) |
| 后端 | Python 3.11+ / FastAPI / SSE |
| 前端 | React 18 + TypeScript + Vite + Tailwind CSS |
| 图表 | ECharts 5 |
| 数据库 | SQLite (WAL 模式) |

## 快速开始

### 1. 环境准备

```bash
# Python 3.11+
# Node.js 18+
```

### 2. 后端

```bash
cd backend

# 创建虚拟环境
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 配置环境变量（复制模板并填入 API Key）
copy ..\.env.example ..\.env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 生成模拟数据（首次运行）
python data_generator.py

# 启动后端
uvicorn main:app --reload --port 8000
```

### 3. 前端

```bash
cd frontend

npm install
npm run dev
```

### 4. 打开浏览器

访问 http://localhost:5173

## 演示场景

| 用户问题 | 期望回答 |
|----------|----------|
| "现在停车场还剩多少车位？" | 空余车位数 + 占用率图表 |
| "现在停车场新能源车的比例？" | 占比数据 + 饼图 |
| "最近一个月停车数变化趋势？" | 趋势分析 + 折线图 |

## 项目结构

```
├── backend/
│   ├── main.py              # FastAPI 入口 + SSE 端点
│   ├── config.py            # 配置（API key, DB, model）
│   ├── agent.py             # ReAct Agent 循环
│   ├── tools/
│   │   ├── __init__.py      # Tool registry
│   │   ├── parking.py       # T1-T7 停车场业务工具
│   │   ├── sql_tool.py      # T8 受控 SQL 查询
│   │   └── chart_tool.py    # T9 图表渲染
│   ├── db.py                # SQLite 连接 + Schema
│   ├── data_generator.py    # 模拟数据生成
│   ├── models.py            # Pydantic 模型
│   ├── sse.py               # SSE 事件发送器
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── components/      # React 组件
│   │   ├── hooks/           # useChat SSE Hook
│   │   └── types/           # TypeScript 类型
│   └── package.json
├── data/                    # SQLite 数据库存储
├── docs/SPEC.md             # 技术规范文档
└── .env.example             # 环境变量模板
```

## 工具体系

| 工具 | 功能 |
|------|------|
| `get_current_vacancy` | 查询当前空余车位数和占用情况 |
| `get_nev_ratio` | 查询新能源车占比 |
| `get_trend` | 查询停车趋势（含7日移动平均） |
| `get_floor_status` | 查询楼层占用情况 |
| `get_hourly_distribution` | 查询时段进出分布 |
| `get_vehicle_detail` | 按车牌查询车辆详情 |
| `get_summary_stats` | 查询汇总统计 |
| `sql_query` | 受控只读 SQL 查询 |
| `render_chart` | 生成 ECharts 图表 |

## 数据说明

- 停车场：800 个车位 / 4 层
- 历史数据：120 天
- 车辆类型：ICE(燃油) 55%, BEV(纯电动) 25%, PHEV(插电混动) 12%, HEV(油电混动) 8%
- 时间模式：早晚高峰 + 周末效应

## License

MIT
