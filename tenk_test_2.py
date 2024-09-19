import pandas as pd
from edgar import *
from edgar.financials import Financials
from fuzzywuzzy import process

# Set EDGAR identity
set_identity("Curtis Gile curtis.j.gile@gmail.com")

# Function to perform fuzzy matching of labels between DataFrames
def fuzzy_merge(df1, df2, key1, key2, threshold=80, limit=1):
    s = df2[key2].tolist()
    matches = df1[key1].apply(lambda x: process.extract(x, s, limit=limit))
    df1['best_match'] = matches.apply(lambda x: x[0][0] if x[0][1] >= threshold else None)
    df1['match_score'] = matches.apply(lambda x: x[0][1] if x[0][1] >= threshold else None)
    
    # Merge on the best fuzzy match
    merged_df = pd.merge(df1, df2, left_on='best_match', right_on=key2, how='left', suffixes=('', '_duplicate'))
    
    # Remove helper columns after merge
    merged_df.drop(columns=['best_match', 'match_score'], inplace=True)
    
    return merged_df

# Function to clean up merged DataFrame
def clean_merged_df(df):
    # Reset index to align rows and avoid index alignment issues
    df = df.reset_index(drop=True)

    # Get a list of original and duplicate columns to compare
    years = [col for col in df.columns if col.isdigit()]
    duplicate_years = [col for col in df.columns if col.endswith('_duplicate')]

    for year, duplicate_year in zip(years, duplicate_years):
        # Drop rows where either original or duplicate column is missing
        df.dropna(subset=[year, duplicate_year], how='any', inplace=True)

        # Extract column values and flatten them to 1D arrays
        original_values = df[year].values.flatten()
        duplicate_values = df[duplicate_year].values.flatten()

        # Create a boolean mask where values match between original and duplicate columns, considering NaNs
        match_mask = (original_values == duplicate_values) | (pd.isna(original_values) & pd.isna(duplicate_values))

        # If there are rows where the values match, keep those rows
        if match_mask.any():
            df = df.loc[match_mask]
        else:
            # Otherwise, keep the row with the highest value in the original column
            df = df.loc[df.groupby('label')[year].transform('max') == df[year]]

        # Drop the duplicate column
        df.drop(columns=[duplicate_year], inplace=True)

    # Remove any duplicate rows based on the 'label' column, keeping the first occurrence
    df = df.drop_duplicates(subset=['label'], keep='first')

    return df





# Get the latest four 10-K filings
filings = Company("AAPL").get_filings(form="10-K").latest(4)

# Extract balance sheets from the filings
balance_sheets = []
for filing in filings:
    tenk = filing.obj()
    financials = tenk.financials
    balance_sheet = financials.get_balance_sheet().get_dataframe()
    
    # Reset index to move labels into a column
    balance_sheet.reset_index(inplace=True)
    balance_sheet.rename(columns={'index': 'label'}, inplace=True)
    
    # Debug: Print columns to check structure
    print(f"Balance sheet columns: {balance_sheet.columns}")
    
    # Check if 'label' column exists after renaming
    if 'label' not in balance_sheet.columns:
        print("Error: 'label' column not found in balance sheet DataFrame. Skipping this balance sheet.")
        continue
    
    balance_sheets.append(balance_sheet)

# Check if there are any balance sheets to join
if not balance_sheets:
    print("No balance sheets available for fuzzy join. Exiting.")
else:
    # Perform fuzzy joins sequentially between the balance sheets
    fuzzy_joined_df = balance_sheets[0]
    for i in range(1, len(balance_sheets)):
        fuzzy_joined_df = fuzzy_merge(fuzzy_joined_df, balance_sheets[i], 'label', 'label')
    
    # Ensure 'label' column is preserved in the final DataFrame
    if 'label' not in fuzzy_joined_df.columns:
        print("Error: 'label' column missing in final merged DataFrame.")
    else:
        # Clean up the merged DataFrame using the new logic
        cleaned_df = clean_merged_df(fuzzy_joined_df)

        # Write the final DataFrame to a text file
        with open('merged_balance_sheets_output_cleaned.txt', 'w') as f:
            f.write(cleaned_df.to_string())
        
        print("Final cleaned merged DataFrame has been written to 'merged_balance_sheets_output_cleaned.txt'.")
