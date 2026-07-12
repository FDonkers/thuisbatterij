#!/usr/bin/env python3
from pathlib import Path
import time
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_CSV = BASE_DIR / "energieverbruik" / "energie_verbruik_2025Q3_2026Q2.csv"
INPUT_CSV = BASE_DIR / "energieverbruik" / "P1e-2025-7-1-2026-7-1.csv"
START_DATE = pd.Timestamp("2025-07-01 00:00:00")
END_DATE = pd.Timestamp("2026-06-30 23:59:59")

def format_value(value: float) -> str:
    return f"{value:.6f}"

def read_source_csv(path: Path) -> pd.DataFrame:
    columns = [
        "datum_nl", 
        "Import T1 kWh", 
        "Import T2 kWh", 
        "Export T1 kWh", 
        "Export T2 kWh", 
        "L1 max W", 
        "L2 max W", 
        "L3 max W"
        ]
    df = pd.read_csv(
        path,
        sep=",",
        decimal=".",
        skiprows=1,
        header=None,
        names=columns,
        encoding="utf-8",
    )

    # drop unnecessary columns
    df = df.drop(["L1 max W","L2 max W","L3 max W"], axis=1)

    # filter on date range
    df["datum_nl"] = pd.to_datetime(df["datum_nl"], format="%Y-%m-%d %H:%M", errors="coerce")
    df = df[df["datum_nl"] >= START_DATE].copy()
    df = df[df["datum_nl"] <= END_DATE].copy()
    df = df.sort_values("datum_nl").reset_index(drop=True)

    # calculate energy usage per 15-minute interval from cumulative meter readings
    df["total_import_kWh"] = df["Import T1 kWh"] + df["Import T2 kWh"]
    df["total_export_kWh"] = df["Export T1 kWh"] + df["Export T2 kWh"]
    df["energy_usage_kWh_per_15m"] = (
        df["total_import_kWh"].diff().fillna(0.0)
        - df["total_export_kWh"].diff().fillna(0.0)
    )

    # drop unnecessary columns
    df = df.drop(["Import T1 kWh","Import T2 kWh"], axis=1)
    df = df.drop(["Export T1 kWh","Export T2 kWh"], axis=1)
    return df


def main() -> None:
    frames = []
    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Input file not found: {INPUT_CSV}")
    frames.append(read_source_csv(INPUT_CSV))

    df = pd.concat(frames, ignore_index=True)

    if df.empty:
        raise ValueError("No data found for the requested period")
    
    
    print(df.head(5))
    print(".....")
    print(df.tail(5))

    time_slots = [f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in (0, 15, 30, 45)]
    header = ["date", *time_slots, "total", "minimum", "average", "maximum"]

    rows = []
    for day, day_df in df.groupby(df["datum_nl"].dt.normalize()):
        ordered = day_df.sort_values("datum_nl")
        values = ordered["energy_usage_kWh_per_15m"].tolist()
        if len(values) != len(time_slots):
            values = values[: len(time_slots)]
            if len(values) < len(time_slots):
                values.extend([float("nan")] * (len(time_slots) - len(values)))

        total = float(sum(values))
        minimum = float(min(values))
        maximum = float(max(values))
        average = total / len(values)

        row = [day.strftime("%Y-%m-%d")]
        row.extend(format_value(value) if pd.notna(value) else "" for value in values)
        row.extend([
            format_value(total),
            format_value(minimum),
            format_value(average),
            format_value(maximum),
        ])
        rows.append(row)

    OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    output_df = pd.DataFrame(rows, columns=header)
    output_df.to_csv(OUTPUT_CSV, index=False, lineterminator="\n")

    print(f"Wrote {len(rows)} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
