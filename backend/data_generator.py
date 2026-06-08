"""
模拟停车场数据生成器。

基于泊松分布模拟车辆到达，指数分布模拟停车时长。
生成 120 天历史数据，覆盖早晚高峰和周末模式。
采用容量感知的时间线模拟，确保任意时刻在场车辆数 ≤ 总车位数。
"""

import datetime
import heapq
import math
import random
import sqlite3
import sys
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


def _poisson_sample(lam: float) -> int:
    """泊松分布采样。
    
    lam >= 30 时用正态近似 N(lam, lam)，效率更高；
    lam < 30 时用 Knuth 指数累加法，保证小样本精度。
    """
    if lam <= 0:
        return 0
    if lam < 30:
        # Knuth 算法：累乘均匀随机数直到小于 exp(-lambda)
        L = math.exp(-lam)
        k = 0
        p = 1.0
        while p > L:
            k += 1
            p *= random.random()
        return k - 1
    else:
        # 正态近似 —— 泊松(λ) ≈ N(λ, λ) when λ ≥ 30
        return max(0, int(random.gauss(lam, math.sqrt(lam)) + 0.5))


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
    """指数分布采样停车时长（小时），上限 24h。返回值始终 ≥ 0。"""
    mean = PARKING_DURATION_MEAN_WEEKEND if is_weekend else PARKING_DURATION_MEAN_BUSINESS
    duration = random.expovariate(1.0 / mean)
    return min(duration, 24.0)


def generate(progress_callback=None) -> int:
    """
    生成 120 天历史数据。返回总记录数。

    采用容量感知的时间线模拟：
    - 维护一个按离开时间排序的 min-heap 追踪在场车辆
    - 车辆到达时检查在场数 < TOTAL_SPOTS，满场则跳过
    - 离开时间晚于当前时刻的车辆记录为 exit_time = NULL（至今在场）

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
    now = datetime.datetime.now()  # 只获取一次，作为"当前时刻"
    start_date = today - datetime.timedelta(days=HISTORY_DAYS)
    total_records = 0

    # 容量感知状态
    # heap: exit_dt 的 min-heap，存放 exit_dt <= now 的在场车辆
    # parked_forever: exit_dt > now 的车辆计数（它们在场直到模拟结束，不加入 heap）
    heap = []
    parked_forever = 0

    for day_offset in range(HISTORY_DAYS):
        current_date = start_date + datetime.timedelta(days=day_offset)
        is_weekend = current_date.weekday() >= 5  # 周六日

        daily_mean = _daily_traffic_mean(is_weekend)
        records = []

        for hour in range(24):
            hour_start = datetime.datetime.combine(
                current_date, datetime.time(hour, 0, 0)
            )

            # ── 1. 清理本小时开始前已离开的车辆 ──
            while heap and heap[0] <= hour_start:
                heapq.heappop(heap)

            # ── 2. 采样本小时到达车辆数 ──
            hour_mean = daily_mean * _hour_multiplier(hour, is_weekend) / 24.0
            arrivals = _poisson_sample(hour_mean)
            arrivals = min(arrivals, 200)  # 单小时上限

            # ── 3. 逐车处理到达 ──
            for _ in range(arrivals):
                current_occupied = len(heap) + parked_forever
                if current_occupied >= TOTAL_SPOTS:
                    break  # 满场，本小时后续到达全部跳过

                minute = random.randint(0, 59)
                second = random.randint(0, 59)
                entry_dt = hour_start + datetime.timedelta(
                    minutes=minute, seconds=second
                )

                duration_hours = _sample_parking_duration(is_weekend)
                exit_dt = entry_dt + datetime.timedelta(hours=duration_hours)

                vehicle_type = _generate_vehicle_type()
                plate = _generate_plate(total_records + len(records))
                floor = random.randint(1, FLOORS)
                spot = random.randint(1, SPOTS_PER_FLOOR)

                if exit_dt > now:
                    # 至今未离开
                    exit_time_str = None
                    parked_forever += 1
                else:
                    exit_time_str = exit_dt.isoformat(sep=" ")
                    heapq.heappush(heap, exit_dt)

                records.append((
                    plate,
                    vehicle_type,
                    entry_dt.isoformat(sep=" "),
                    exit_time_str,
                    floor,
                    spot,
                ))

        # ── 批量插入当天数据 ──
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

    # ── 验证 ──
    parked = conn.execute(
        "SELECT COUNT(*) FROM vehicle_record WHERE exit_time IS NULL"
    ).fetchone()[0]
    total = conn.execute("SELECT COUNT(*) FROM vehicle_record").fetchone()[0]
    date_range = conn.execute(
        "SELECT MIN(entry_time), MAX(entry_time) FROM vehicle_record"
    ).fetchone()

    print(f"\n数据生成完成：")
    print(f"  总记录数: {total}")
    print(f"  在场车辆: {parked}  (容量上限: {TOTAL_SPOTS})")
    print(f"  日期范围: {date_range[0][:10]} 至 {date_range[1][:10]}")

    # 容量一致性验证：在场车辆数不应超过总车位数
    if parked > TOTAL_SPOTS:
        print(f"  [WARN] 在场车辆数 ({parked}) 超过总车位数 ({TOTAL_SPOTS})！")
    else:
        print(f"  [OK] 在场车辆数在容量范围内")

    # 抽样验证：检查几个时间点的历史在场数
    sample_times = [
        (start_date + datetime.timedelta(days=30)).isoformat() + " 12:00:00",
        (start_date + datetime.timedelta(days=60)).isoformat() + " 18:00:00",
        (start_date + datetime.timedelta(days=90)).isoformat() + " 08:00:00",
        today.isoformat() + " 10:00:00",
    ]
    print(f"\n历史时刻在场数抽样验证：")
    all_ok = True
    for sample_time in sample_times:
        count = conn.execute(
            "SELECT COUNT(*) FROM vehicle_record "
            "WHERE entry_time <= ? AND (exit_time IS NULL OR exit_time > ?)",
            (sample_time, sample_time),
        ).fetchone()[0]
        status = "OK" if count <= TOTAL_SPOTS else "OVER"
        if count > TOTAL_SPOTS:
            all_ok = False
        print(f"  {sample_time[:16]}: {count} 辆 [{status}]")

    if all_ok:
        print(f"  所有抽样时刻在场数 <= {TOTAL_SPOTS}，容量一致。")
    else:
        print(f"  [WARN] 存在超限时刻，请检查生成逻辑。")

    conn.close()
    return total_records


if __name__ == "__main__":
    generate()
