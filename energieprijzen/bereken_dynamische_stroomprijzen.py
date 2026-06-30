from importlib.resources import path
from pathlib import Path
import pandas as pd
import numpy as np
import argparse

TAXRATE = 1.21;  # 21% tax rate
ENERGY_TAX = 0.11;  # Energy tax in euros per kWh
BASE = Path(__file__).resolve().parents[1]
SRC_DIR = BASE / 'energieprijzen'
INFILE_2025 = SRC_DIR / 'jeroen_punt_nl_dynamische_stroomprijzen_jaar_2025.csv'
INFILE_2026 = SRC_DIR / 'jeroen_punt_nl_dynamische_stroomprijzen_jaar_2026.csv'
OUT_DIR = BASE / 'energieprijzen'
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUTFILE = OUT_DIR / 'jeroen_punt_nl_dynamische_stroomprijzen_2025Q3_2026Q2.csv'

def read_supplier_costs(supplier_name: str) -> float:
    base = Path(__file__).resolve().parents[1]
    src_dir = base / 'energieprijzen'
    suppliers = src_dir / 'leveranciers.csv'
    if not suppliers.exists():
        raise FileNotFoundError('Expected source CSVs not found')
    return float(
        pd.read_csv(suppliers, sep=';', index_col=0).loc[supplier_name, 'verkoopprijs']
        .replace('€', '').strip()
        .replace(',', '.')
    )

def read_prices(path: Path, start=None, end=None) -> pd.DataFrame:
    df = pd.read_csv(
        path,
        sep=';',
        skiprows=1,
        names=['datum_nl', 'datum_utc', 'prijs_excl_belastingen'],
        decimal=',',
        parse_dates=['datum_nl'],
    )
    if start is not None:
        df = df[df['datum_nl'] >= pd.to_datetime(start)]
    if end is not None:
        df = df[df['datum_nl'] < pd.to_datetime(end)]
    return df

def read_prices_jeroen(start=None, end=None) -> pd.DataFrame:
    if not INFILE_2025.exists() or not INFILE_2026.exists():
        raise FileNotFoundError('Expected source CSVs not found')

    df1 = read_prices(INFILE_2025, start=start)
    df2 = read_prices(INFILE_2026, end=end)
    df = pd.concat([df1, df2], ignore_index=True)
    return df

def build_daily_rows(df: pd.DataFrame, taxrate: float, energy_tax: float, supplier_costs: float) -> pd.DataFrame:
    df = df.sort_values('datum_nl').copy()
    df['date'] = df['datum_nl'].dt.date

    rows = []
    for date, group in df.groupby('date'):
        prices = group['prijs_excl_belastingen'].tolist()
        # Ensure 24*4 = 96 samples per day, pad with NaN if missing
        if len(prices) < 96:
            prices = prices + [np.nan] * (96 - len(prices))
        elif len(prices) > 96:
            prices = prices[:96]

        nums = pd.to_numeric(prices, errors='coerce')
        nums = nums * taxrate + energy_tax + supplier_costs  # Apply taxes and supplier costs;

        total = nums.sum()
        minimum = nums.min()
        average = nums.mean()
        maximum = nums.max()

        row = [pd.to_datetime(date).date()] + nums.tolist() + [total, minimum, average, maximum]
        rows.append(row)

    times = [(pd.Timestamp('2025-01-01') + pd.Timedelta(minutes=15*i)).strftime('%H:%M') for i in range(96)]
    cols = ['date'] + times + ['total', 'min', 'avg', 'max']
    out = pd.DataFrame(rows, columns=cols)
    return out


def main():
    parser = argparse.ArgumentParser(description='Calculate energy prices from raw data')
    parser.add_argument('--start-date', type=str, default='2025-07-01',
                        help='Start date in format YYYY-MM-DD (default: 2025-07-01)')
    parser.add_argument('--end-date', type=str, default='2026-07-01',
                        help='End date in format YYYY-MM-DD (default: 2026-07-01)')
    parser.add_argument('--supplier', type=str, default='GreenChoice',
                        help='Energy supplier name (default: GreenChoice)')
    
    args = parser.parse_args()
    START_DATE = args.start_date
    END_DATE = args.end_date
    SUPPLIER = args.supplier

    SUPPLIER_COSTS = read_supplier_costs(SUPPLIER);
    df = read_prices_jeroen(start=START_DATE, end=END_DATE);
    out = build_daily_rows(df, TAXRATE, ENERGY_TAX, SUPPLIER_COSTS)
    out.to_csv(OUTFILE, index=False, float_format='%.6f', header=True)
    print(f'Wrote {OUTFILE}')

if __name__ == '__main__':
    main()
