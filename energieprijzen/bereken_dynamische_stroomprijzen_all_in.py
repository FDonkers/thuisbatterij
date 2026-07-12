from entsoe import EntsoePandasClient
from importlib.resources import path
from pathlib import Path
from unittest import case
import pandas as pd
import numpy as np
import argparse

ENTSOE_API_TOKEN = '6f8dd8c9-231f-4466-b576-e566c41cdfc0'
TAXRATE = 1.21;  # 21% tax rate
ENERGY_TAX = 0.11;  # Energy tax in euros per kWh
BASE = Path(__file__).resolve().parents[1]
DATA_DIR = BASE / 'energieprijzen'
INFILE_2025 = DATA_DIR / 'jeroen_punt_nl_dynamische_stroomprijzen_jaar_2025.csv'
INFILE_2026 = DATA_DIR / 'jeroen_punt_nl_dynamische_stroomprijzen_jaar_2026.csv'
LEVERANCIERS_CSV = DATA_DIR / 'jeroen_punt_nl_leveranciers.csv'

def read_supplier_costs(supplier_name: str) -> float:
    if not LEVERANCIERS_CSV.exists():
        raise FileNotFoundError('Expected source CSVs not found')
    return float(
        pd.read_csv(LEVERANCIERS_CSV, sep=';', index_col=0).loc[supplier_name, 'verkoopprijs']
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
    print("\nSuccess! Here is a sample of the data:")
    return df

def read_prices_entsoe(start=None, end=None) -> pd.DataFrame:
    client = EntsoePandasClient(api_key=ENTSOE_API_TOKEN)

    # 2. Define your time window (must be timezone-aware)
    start = pd.Timestamp(start, tz='Europe/Amsterdam')
    end = pd.Timestamp(end, tz='Europe/Amsterdam')

    # 3. Define the target bidding zone (e.g., DE_LU for Germany/Luxembourg)
    # Other examples: 'FR' (France), 'NL' (Netherlands), 'DK_1' (Denmark 1)
    bidding_zone = 'NL' 

    try:
        # 4. Fetch Day-Ahead Prices
        print("Fetching data..." + f" Start: {start}, End: {end}, Bidding Zone: {bidding_zone}")
        s = client.query_day_ahead_prices(bidding_zone, start=start, end=end)
        df = s.to_frame(name='prijs_excl_belastingen')
        df = df.reset_index()
        df.columns = ['datum_nl', 'prijs_excl_belastingen']
        df.iloc[:, -1] = df.iloc[:, -1]/1000  # Convert from €/MWh to €/kWh         
    except Exception as e:
        print(f"An error occurred: {e}")
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
    cols = ['date'] + times + ['total', 'minimum', 'average', 'maximum']
    out = pd.DataFrame(rows, columns=cols)
    return out


def main():
    parser = argparse.ArgumentParser(description='Calculate energy prices from raw data')
    parser.add_argument('--bron', type=str, default='jeroenpuntnl',
                        help='Source of energy prices (default: jeroenpuntnl)')
    parser.add_argument('--start-date', type=str, default='2025-07-01',
                        help='Start date in format YYYY-MM-DD (default: 2025-07-01)')
    parser.add_argument('--end-date', type=str, default='2026-07-01',
                        help='End date in format YYYY-MM-DD (default: 2026-07-01)')
    parser.add_argument('--supplier', type=str, default='GreenChoice',
                        help='Energy supplier name (default: GreenChoice)')
    
    args = parser.parse_args()
    BRON = args.bron
    START_DATE = args.start_date
    END_DATE = args.end_date
    SUPPLIER = args.supplier
    SUPPLIER_COSTS = read_supplier_costs(SUPPLIER)
    if BRON == 'jeroenpuntnl':
        print(f'Calculating energy prices from {BRON} for supplier {SUPPLIER} from {START_DATE} to {END_DATE}')
        df = read_prices_jeroen(start=START_DATE, end=END_DATE)
    elif BRON == 'entsoe':
        print(f'Calculating energy prices from {BRON} for supplier {SUPPLIER} from {START_DATE} to {END_DATE}')
        df = read_prices_entsoe(start=START_DATE, end=END_DATE)
    else:
        raise ValueError(f'Unsupported source: {BRON}')

    out = build_daily_rows(df, TAXRATE, ENERGY_TAX, SUPPLIER_COSTS)

    # Display the first and last few rows of the pandas DataFrame
    print(out.head(5))
    print(".....")
    print(out.tail(5))

    OUTFILE = DATA_DIR / f'dynamische_stroomprijzen_{BRON}_{SUPPLIER}_{START_DATE}_{END_DATE}_all_in.csv'  
    out.to_csv(OUTFILE, index=False, float_format='%.6f', header=True)
    print(f'Wrote {OUTFILE}')

if __name__ == '__main__':
    main()
