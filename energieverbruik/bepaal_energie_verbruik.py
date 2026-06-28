#!/usr/bin/env python3
from pathlib import Path
import pandas as pd


BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_CSV = BASE_DIR / "results" / "energie_verbruik_2025Q3_2026Q2.csv"
INPUT_FILES = [
    BASE_DIR / "data" / "jeroen_punt_nl_dynamische_stroomprijzen_jaar_2025.csv",
    BASE_DIR / "data" / "jeroen_punt_nl_dynamische_stroomprijzen_jaar_2026.csv",
]


def format_value(value: float) -> str:
    return f"{value:.6f}"


def read_source_csv(path: Path) -> pd.DataFrame:
    columns = ["datum_nl", "datum_utc", "prijs_excl_belastingen"]
    df = pd.read_csv(
        path,
        sep=";",
        decimal=",",
        skiprows=1,
        header=None,
        names=columns,
        encoding="utf-8",
    )

    df["datum_nl"] = pd.to_datetime(df["datum_nl"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    df["datum_utc"] = pd.to_datetime(df["datum_utc"], format="%Y-%m-%d %H:%M:%S", errors="coerce")
    df["prijs_excl_belastingen"] = pd.to_numeric(df["prijs_excl_belastingen"], errors="coerce")

    return df.dropna(subset=["datum_nl", "prijs_excl_belastingen"]).copy()


def main() -> None:
    frames = []
    for input_csv in INPUT_FILES:
        if not input_csv.exists():
            raise FileNotFoundError(f"Input file not found: {input_csv}")
        frames.append(read_source_csv(input_csv))

    df = pd.concat(frames, ignore_index=True)
    df = df[df["datum_nl"] >= pd.Timestamp("2025-07-01 00:00:00")].copy()
    df = df[df["datum_nl"] < pd.Timestamp("2026-06-01 00:00:00")].copy()
    df = df.sort_values("datum_nl").reset_index(drop=True)

    if df.empty:
        raise ValueError("No data found for the requested period")

    time_slots = [f"{hour:02d}:{minute:02d}" for hour in range(24) for minute in (0, 15, 30, 45)]
    header = ["date", *time_slots, "total", "minimum", "average", "maximum"]

    rows = []
    for day, day_df in df.groupby(df["datum_nl"].dt.normalize()):
        ordered = day_df.sort_values("datum_nl")
        values = ordered["prijs_excl_belastingen"].tolist()
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
