"""
模拟停车场数据生成器。

基于泊松分布模拟车辆到达，指数分布模拟停车时长。
生成 120 天历史数据，覆盖早晚高峰和周末模式。
"""

import datetime
import random
import sqlite3
import sys
import math
from pathlib import Path
from typing import Optional

import config
from db import init_db, seed_config

# ── 参数 ──────────────────────────────────────────────
HISTORY_DAYS = 120
TOTAL_SPOTS = 800
FLOORS = 4
SPOTS_PER_FLOOR = 200
DAILY_TRAFFIC_MIN = 1200
DAILY_TRAFFIC_MAX = 1800
# 车辆类型分布
VEHICLE_TYPE_WEIGHTS = {
    "ICE": 0.55,
    "BEV": 0.25,
    "PHEV": 0.12,
    "HEV": 0.08,
}
VEHICLE_TYPES = list(VEHICLE_TYPE_WEIGHTS.keys())
VEHICLE_PROBS = list(VEHICLE_TYPE_WEIGHTS.values())

# 停车时长参数（指数分布均值，单位：小时）
PARKING_DURATION_MEAN_BUSINESS = 3.0  # 工作日
PARKING_DURATION_MEAN_WEEKEND = 4.5

# 高峰参数
MORNING_PEAK = (7, 9, 1.6)   # (start, end, multiplier)
LUNCH_PERIOD = (11, 14, 1.2)
EVENING_PEAK = (17, 19, 1.8)
NIGHT_LULL = (21, 24, 0.3)    # 21:00-24:00
NIGHT_LULL2 = (0, 6, 0.1)     # 0:00-6:00

random.seed(42)


def _hour_multiplier(hour: int, is_weekend: bool) -> float:
    """返回某小时的进入流倍率."""
    base = 1.0
    if is_weekend:
        base *= 0.70  # 周末整体降低 30%

    if MORNING_PEAK[0] <= hour < MORNING_PEAK[1]:
        return base * MORNING_PEAK[2]
    elif LUNCH_PERIOD[0] <= hour < LUNCH_PERIOD[1]:
        return base * LUNCH_PERIOD[2]
    elif EVENING_PEAK[0] <= hour < EVENING_PEAK[1]:
        return base * EVENING_PEAK[2]
    elif NIGHT_LULL[0] <= hour < NIGHT_LULL[1]:
        return base * NIGHT_LULL[2]
    elif 0 <= hour < NIGHT_LULL2[1]:
        return base * NIGHT_LULL2[2]
    else:
        return base * 0.8


def _daily_traffic_mean(is_weekend: bool) -> float:
    """日均车流量期望值."""
    base = random.randint(DAILY_TRAFFIC_MIN, DAILY_TRAFFIC_MAX)
    return base * (0.7 if is_weekend else 1.0)


def _generate_plate(index: int) -> str:
    """生成模拟车牌."""
    provinces = ["京", "沪", "粤", "苏", "浙", "鲁", "川", "鄂"]
    return f"{random.choice(provinces)}{chr(65 + random.randint(0, 25))}{index % 100000:05d}"


def _generate_vehicle_type() -> str:
    """按权重随机生成车辆类型."""
    return random.choices(VEHICLE_TYPES, weights=VEHICLE_PROBS, k=1)[0]


def _sample_parking_duration(is_weekend: bool) -> float:
    """指数分布采样停车时长（小时）."""
    mean = PARKING_DURATION_MEAN_WEEKEND if is_weekend else PARKING_DURATION_MEAN_BUSINESS
    duration = random.expovariate(1.0 / mean)
    return min(duration, 24.0)  # 最大 24h 截断


def generate(progress_callback=None) -> int:
    """
    生成 120 天历史数据。返回总记录数。
    progress_callback(day_index, total_days): 进度回调。
    """
    print("初始化数据库...")
    init_db()
    seed_config()

    conn = sqlite3.connect(config.DATABASE_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("DELETE FROM vehicle_record")  # 清空旧数据

    today = datetime.date.today()
    start_date = today - datetime.timedelta(days=HISTORY_DAYS)
    total_records = 0

    for day_offset in range(HISTORY_DAYS):
        current_date = start_date + datetime.timedelta(days=day_offset)
        is_weekend = current_date.weekday() >= 5  # 周六日

        daily_mean = _daily_traffic_mean(is_weekend)

        # 每天以秒为单位模拟车辆进入
        records = []
        for hour in range(24):
            hour_mean = daily_mean * _hour_multiplier(hour, is_weekend) / 24.0
            # 泊松分布确定该小时进入车辆数
            arrivals = min(max(1, int(random.gauss(hour_mean, max(hour_mean * 0.15, 2)))), 200)

            for _ in range(arrivals):
                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                entry_dt = datetime.datetime.combine(
                    current_date,
                    datetime.time(hour, minute, second)
                )

                duration_hours = _sample_parking_duration(is_weekend)
                exit_dt = entry_dt + datetime.timedelta(hours=duration_hours)
                
                # 根据数据新旧决定在场概率：
                # 最近 7 天：40-60% 在场；8-30 天：5-10%；更早：0%
                days_ago = (today - current_date).days
                now = datetime.datetime.now()
                if days_ago <= 7:
                    stay_prob = random.uniform(0.40, 0.60)
                elif days_ago <= 30:
                    stay_prob = random.uniform(0.05, 0.10)
                else:
                    stay_prob = 0.0
                
                is_still_parked = random.random() < stay_prob and days_ago <= 7
                # 也保留原始的跨天在场逻辑
                if not is_still_parked:
                    is_still_parked = (exit_dt > now)
                
                if exit_dt < entry_dt:
                    exit_dt = entry_dt + datetime.timedelta(hours=1.0)  # 最少停 1 小时

                vehicle_type = _generate_vehicle_type()
                plate = _generate_plate(total_records + len(records))
                floor = random.randint(1, FLOORS)
                spot = random.randint(1, SPOTS_PER_FLOOR)

                records.append((
                    plate,
                    vehicle_type,
                    entry_dt.isoformat(sep=" "),
                    None if is_still_parked else exit_dt.isoformat(sep=" "),
                    floor,
                    spot,
                ))

        # 批量插入
        conn.executemany(
            "INSERT INTO vehicle_record (plate, vehicle_type, entry_time, exit_time, entry_floor, entry_spot) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            records,
        )
        total_records += len(records)

        if progress_callback:
            progress_callback(day_offset, HISTORY_DAYS)
        else:
            if (day_offset + 1) % 10 == 0 or day_offset == HISTORY_DAYS - 1:
                print(f"  进度: {day_offset + 1}/{HISTORY_DAYS} 天, 累计 {total_records} 条记录")

    conn.commit()

    # 验证
    parked = conn.execute(
        "SELECT COUNT(*) FROM vehicle_record WHERE exit_time IS NULL"
    ).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM vehicle_record").fetchone()[0]
    date_range = conn.execute(
        "SELECT MIN(entry_time), MAX(entry_time) FROM vehicle_record"
    ).fetchone()

    print(f"\n数据生成完成：")
    print(f"  总记录数: {total}")
    print(f"  在场车辆: {parked}")
    print(f"  日期范围: {date_range[0][:10]} 至 {date_range[1][:10]}")

    conn.close()
    return total_records


if __name__ == "__main__":
    generate()
