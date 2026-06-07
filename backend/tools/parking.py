"""
停车场业务工具 T1-T7。

每个工具从 SQLite 查询数据，返回结构化字典。
"""

import datetime
import json
from typing import Any, Optional

import pandas as pd

from db import get_db


def get_current_vacancy() -> dict:
    """T1: 查询当前空余车位数和占用情况。"""
    with get_db(read_only=True) as conn:
        config = conn.execute("SELECT total_spots FROM parking_lot_config WHERE id = 1").fetchone()
        total_spots = config["total_spots"] if config else 800

        occupied = conn.execute(
            "SELECT COUNT(*) AS cnt FROM vehicle_record WHERE exit_time IS NULL"
        ).fetchone()["cnt"]

        last_updated = conn.execute(
            "SELECT MAX(entry_time) AS t FROM vehicle_record"
        ).fetchone()["t"]

    vacant = total_spots - occupied
    vacancy_rate = round(vacant / total_spots, 4) if total_spots > 0 else 0.0

    return {
        "total_spots": total_spots,
        "occupied": occupied,
        "vacant": vacant,
        "vacancy_rate": vacancy_rate,
        "last_updated": last_updated,
    }


def get_nev_ratio(include_hev: bool = False) -> dict:
    """T2: 查询当前停车场内新能源车占比。"""
    with get_db(read_only=True) as conn:
        rows = conn.execute(
            "SELECT vehicle_type, COUNT(*) AS cnt "
            "FROM vehicle_record WHERE exit_time IS NULL "
            "GROUP BY vehicle_type"
        ).fetchall()

    breakdown = [{"type": r["vehicle_type"], "count": r["cnt"]} for r in rows]
    total_parked = sum(item["count"] for item in breakdown)

    nev_types = {"BEV", "PHEV"}
    if include_hev:
        nev_types.add("HEV")

    nev_count = sum(item["count"] for item in breakdown if item["type"] in nev_types)
    nev_ratio = round(nev_count / total_parked, 4) if total_parked > 0 else 0.0

    type_names = {"ICE": "燃油车", "BEV": "纯电动", "PHEV": "插电混动", "HEV": "油电混动"}
    for item in breakdown:
        item["name"] = type_names.get(item["type"], item["type"])
        item["percentage"] = round(item["count"] / total_parked, 4) if total_parked > 0 else 0.0

    return {
        "total_parked": total_parked,
        "nev_count": nev_count,
        "nev_ratio": nev_ratio,
        "breakdown": breakdown,
    }


def get_trend(days: int = 30) -> list[dict]:
    """T3: 查询最近N天停车数变化趋势。"""
    days = min(max(days, 1), 120)

    with get_db(read_only=True) as conn:
        total_spots_row = conn.execute(
            "SELECT total_spots FROM parking_lot_config WHERE id = 1"
        ).fetchone()
        total_spots = total_spots_row["total_spots"] if total_spots_row else 800

        rows = conn.execute(
            "SELECT DATE(entry_time) AS date, "
            "COUNT(*) AS entry_count, "
            "SUM(CASE WHEN exit_time IS NOT NULL THEN 1 ELSE 0 END) AS exit_count "
            "FROM vehicle_record "
            "WHERE entry_time >= DATE('now', ? || ' days') "
            "GROUP BY DATE(entry_time) "
            "ORDER BY date",
            (f"-{days}",),
        ).fetchall()

    # 计算每日峰值占用（需逐日计算）
    result = []
    for row in rows:
        date_str = row["date"]
        entry_count = row["entry_count"]
        exit_count = row["exit_count"]

        # 当天约有 ongoing = 当日之前在场 + 当日进入 - 当日离开
        # 简化：用当日净流入 + 前一日存量估计峰值
        # 这里采用入场数作为活跃度指标，峰值占用用入场数 * 0.75 近似
        peak_occupancy = min(int(entry_count * 0.75), total_spots)
        occupancy_rate = round(peak_occupancy / total_spots, 4)

        result.append({
            "date": date_str,
            "entry_count": entry_count,
            "exit_count": exit_count,
            "peak_occupancy": peak_occupancy,
            "occupancy_rate": occupancy_rate,
        })

    # 7 日移动平均
    if len(result) >= 7:
        df = pd.DataFrame(result)
        df["rolling_avg_7d"] = df["peak_occupancy"].rolling(7, min_periods=1).mean().round(1)
        result = df.to_dict(orient="records")

    return result


def get_floor_status(floor: Optional[int] = None) -> list[dict]:
    """T4: 查询各楼层或指定楼层的停车位占用情况。"""
    with get_db(read_only=True) as conn:
        config = conn.execute(
            "SELECT floors, spots_per_floor FROM parking_lot_config WHERE id = 1"
        ).fetchone()
        total_floors = config["floors"] if config else 4
        spots_per_floor = config["spots_per_floor"] if config else 200

        floors_to_query = [floor] if floor else list(range(1, total_floors + 1))

        result = []
        for f in floors_to_query:
            occupied = conn.execute(
                "SELECT COUNT(*) AS cnt FROM vehicle_record "
                "WHERE exit_time IS NULL AND entry_floor = ?",
                (f,),
            ).fetchone()["cnt"]
            result.append({
                "floor": f,
                "total_spots": spots_per_floor,
                "occupied": occupied,
                "vacant": spots_per_floor - occupied,
                "occupancy_rate": round(occupied / spots_per_floor, 4),
            })

    return result


def get_hourly_distribution(date: Optional[str] = None) -> list[dict]:
    """T5: 查询某日各小时车辆进出分布。"""
    if date is None:
        date = datetime.date.today().isoformat()

    with get_db(read_only=True) as conn:
        rows = conn.execute(
            "SELECT CAST(strftime('%H', entry_time) AS INTEGER) AS hour, "
            "COUNT(*) AS entry_count, "
            "SUM(CASE WHEN exit_time IS NOT NULL AND DATE(exit_time) = ? THEN 1 ELSE 0 END) AS exit_count "
            "FROM vehicle_record "
            "WHERE DATE(entry_time) = ? "
            "GROUP BY hour ORDER BY hour",
            (date, date),
        ).fetchall()

    hour_map = {r["hour"]: {"entry_count": r["entry_count"], "exit_count": r["exit_count"]} for r in rows}

    result = []
    for h in range(24):
        data = hour_map.get(h, {"entry_count": 0, "exit_count": 0})
        result.append({
            "hour": h,
            "entry_count": data["entry_count"],
            "exit_count": data["exit_count"],
            "net_change": data["entry_count"] - data["exit_count"],
        })

    return result


def get_vehicle_detail(plate: str) -> Optional[dict]:
    """T6: 按车牌查询车辆进出记录。"""
    with get_db(read_only=True) as conn:
        # 先查在场
        row = conn.execute(
            "SELECT plate, vehicle_type, entry_time, exit_time, entry_floor, entry_spot "
            "FROM vehicle_record WHERE plate = ? AND exit_time IS NULL "
            "ORDER BY entry_time DESC LIMIT 1",
            (plate,),
        ).fetchone()

        if not row:
            # 查最近的已离开记录
            row = conn.execute(
                "SELECT plate, vehicle_type, entry_time, exit_time, entry_floor, entry_spot "
                "FROM vehicle_record WHERE plate = ? "
                "ORDER BY entry_time DESC LIMIT 1",
                (plate,),
            ).fetchone()

        if not row:
            return None

    vehicle_type_names = {"ICE": "燃油车", "BEV": "纯电动", "PHEV": "插电混动", "HEV": "油电混动"}
    current_status = "parked" if row["exit_time"] is None else "left"

    duration_minutes = None
    if row["entry_time"] and row["exit_time"]:
        try:
            entry = datetime.datetime.strptime(row["entry_time"], "%Y-%m-%d %H:%M:%S")
            exit_t = datetime.datetime.strptime(row["exit_time"], "%Y-%m-%d %H:%M:%S")
            duration_minutes = round((exit_t - entry).total_seconds() / 60, 1)
        except (ValueError, TypeError):
            pass
    elif row["entry_time"] and current_status == "parked":
        try:
            entry = datetime.datetime.strptime(row["entry_time"], "%Y-%m-%d %H:%M:%S")
            duration_minutes = round((datetime.datetime.now() - entry).total_seconds() / 60, 1)
        except (ValueError, TypeError):
            pass

    return {
        "plate": row["plate"],
        "vehicle_type": row["vehicle_type"],
        "vehicle_type_name": vehicle_type_names.get(row["vehicle_type"], row["vehicle_type"]),
        "current_status": current_status,
        "entry_time": row["entry_time"],
        "exit_time": row["exit_time"],
        "duration_minutes": duration_minutes,
        "floor": row["entry_floor"],
        "spot": row["entry_spot"],
    }


def get_summary_stats(days: int = 7) -> dict:
    """T7: 查询最近N天汇总统计。"""
    days = min(max(days, 1), 120)

    with get_db(read_only=True) as conn:
        total_spots_row = conn.execute(
            "SELECT total_spots FROM parking_lot_config WHERE id = 1"
        ).fetchone()
        total_spots = total_spots_row["total_spots"] if total_spots_row else 800

        # 总车次
        total_visits = conn.execute(
            "SELECT COUNT(*) AS cnt FROM vehicle_record "
            "WHERE entry_time >= DATE('now', ? || ' days')",
            (f"-{days}",),
        ).fetchone()["cnt"]

        # 平均停车时长
        avg_row = conn.execute(
            "SELECT AVG((julianday(exit_time) - julianday(entry_time)) * 24 * 60) AS avg_minutes "
            "FROM vehicle_record "
            "WHERE exit_time IS NOT NULL "
            "AND entry_time >= DATE('now', ? || ' days')",
            (f"-{days}",),
        ).fetchone()
        avg_duration = round(avg_row["avg_minutes"], 1) if avg_row["avg_minutes"] else 0.0

        # 日均占用率
        daily = conn.execute(
            "SELECT DATE(entry_time) AS date, COUNT(*) AS cnt "
            "FROM vehicle_record "
            "WHERE entry_time >= DATE('now', ? || ' days') "
            "GROUP BY DATE(entry_time)",
            (f"-{days}",),
        ).fetchall()

        avg_occupancy = 0.0
        if daily:
            avg_cnt = sum(r["cnt"] for r in daily) / len(daily)
            avg_occupancy = round(min(avg_cnt * 0.75 / total_spots, 1.0), 4)

        # 新能源占比趋势
        nev_trend_rows = conn.execute(
            "SELECT DATE(entry_time) AS date, "
            "SUM(CASE WHEN vehicle_type IN ('BEV', 'PHEV') THEN 1 ELSE 0 END) AS nev_cnt, "
            "COUNT(*) AS total "
            "FROM vehicle_record "
            "WHERE entry_time >= DATE('now', ? || ' days') "
            "GROUP BY DATE(entry_time) ORDER BY date",
            (f"-{days}",),
        ).fetchall()

        nev_trend = [
            {
                "date": r["date"],
                "ratio": round(r["nev_cnt"] / r["total"], 4) if r["total"] else 0.0,
            }
            for r in nev_trend_rows
        ]

    return {
        "total_visits": total_visits,
        "avg_duration_minutes": avg_duration,
        "avg_occupancy_rate": avg_occupancy,
        "nev_ratio_trend": nev_trend,
    }
