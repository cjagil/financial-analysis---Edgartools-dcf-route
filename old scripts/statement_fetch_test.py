import pandas as pd
from edgar import Company, set_identity
from edgar.financials import Financials
from fuzzywuzzy import fuzz, process

# Set EDGAR identity
set_identity("Curtis Gile curtis.j.gile@gmail.com")

# Define a set of common labels to match against
standard_labels = [
    'Total Assets', 'Total Liabilities', 'Net Income', 'Operating Income',
    'Cash and Cash Equivalents', 'Revenue', 'Gross Profit', 'Total Equity',
    'Research and Development', 'Accounts Payable', 'Long-term Debt',
    'Total Current Assets', 'Total Current Liabilities', 'Earnings Per Share'
]

# Function to standardize labels using fuzzy matching
def standardize_labels(df, label_column):
    # Create a mapping of original labels to standard labels
    label_map = {}
    for label in df[label_column].unique():
        match, score = process.extractOne(label, standard_labels, scorer=fuzz.token_sort_ratio)
        if score > 70:  # Adjust threshold as needed
            label_map[label] = match
        else:
            label_map[label] = label  # Use original if no good match

    # Apply the mapping to the dataframe's label column
    df[label_column] = df[label_column].map(label_map)
    return df

# Create a Company object for the target company (e.g., Apple)
company = Company("AAPL")

# Fetch the latest 5 10-K filings
filings = company.get_filings(form="10-K")[:5]  # Correctly accessing the list of filings

# Initialize lists for storing the financial statement dataframes
balance_sheets_list = []
income_statements_list = []
cash_flows_list = []

# Iterate through each filing to extract financial data
for filing in filings:
    try:
        # Retrieve the XBRL data object
        financials = Financials(filing)

        # Extract balance sheet, income statement, and cash flow statement
        balance_sheet_df = financials.get_balance_sheet().get_dataframe().reset_index()
        income_statement_df = financials.get_income_statement().get_dataframe().reset_index()
        cash_flow_df = financials.get_cash_flow_statement().get_dataframe().reset_index()

        # Add a 'Year' column based on the filing date
        year = filing.filing_date[:4]
        for df in [balance_sheet_df, income_statement_df, cash_flow_df]:
            df['Year'] = year

            # Standardize labels using fuzzy matching
            df = standardize_labels(df, 'label')

        # Append the dataframes to the respective lists
        balance_sheets_list.append(balance_sheet_df)
        income_statements_list.append(income_statement_df)
        cash_flows_list.append(cash_flow_df)
        
    except AttributeError as e:
        print(f"Error processing filing: {e}")
        continue

# Combine dataframes
if balance_sheets_list:
    balance_sheet_combined = pd.concat(balance_sheets_list, ignore_index=True)
    income_statement_combined = pd.concat(income_statements_list, ignore_index=True)
    cash_flow_combined = pd.concat(cash_flows_list, ignore_index=True)

    # Output to Excel for review
    output_path = "/mnt/data/combined_financial_statements.xlsx"
    with pd.ExcelWriter(output_path) as writer:
        balance_sheet_combined.to_excel(writer, sheet_name='Balance Sheet', index=False)
        income_statement_combined.to_excel(writer, sheet_name='Income Statement', index=False)
        cash_flow_combined.to_excel(writer, sheet_name='Cash Flow Statement', index=False)

    print(f"Financial statements successfully written to {output_path}")
else:
    print("No financial data extracted.")
