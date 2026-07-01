import argparse
import pandas as pd
from entsoe import EntsoePandasClient

# 0. get command line arguments for start and end dates
parser = argparse.ArgumentParser(description='Calculate energy prices from raw data')
parser.add_argument('--start-date', type=str, default='2025-07-01',
    help='Start date in format YYYY-MM-DD (default: 2025-07-01)')
parser.add_argument('--end-date', type=str, default='2026-07-01',
    help='End date in format YYYY-MM-DD (default: 2026-07-01)')

args = parser.parse_args()
START_DATE = args.start_date
END_DATE = args.end_date

# 1. Initialize the client with your API token
API_TOKEN = '6f8dd8c9-231f-4466-b576-e566c41cdfc0'
client = EntsoePandasClient(api_key=API_TOKEN)

# 2. Define your time window (must be timezone-aware)
start = pd.Timestamp(START_DATE, tz='Europe/Amsterdam')
end = pd.Timestamp(END_DATE, tz='Europe/Amsterdam')

# 3. Define the target bidding zone (e.g., DE_LU for Germany/Luxembourg)
# Other examples: 'FR' (France), 'NL' (Netherlands), 'DK_1' (Denmark 1)
bidding_zone = 'NL' 

try:
    # 4. Fetch Day-Ahead Prices
    print("Fetching data..." + f" Start: {start}, End: {end}, Bidding Zone: {bidding_zone}")
    df_prices = client.query_day_ahead_prices(bidding_zone, start=start, end=end)
    
    # Display the first and last few rows of the pandas DataFrame
    print("\nSuccess! Here is a sample of the data:")
    print(df_prices.head(5))
    print(".....")
    print(df_prices.tail(5))
    
    # 5. Optional: Save to a CSV file
    df_prices.to_csv('entsoe_dynamische_stroomprijzen_'+START_DATE+'_'+END_DATE+'.csv')

except Exception as e:
    print(f"An error occurred: {e}")