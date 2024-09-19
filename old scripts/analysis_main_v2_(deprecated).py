import pandas as pd
from edgar import *
from edgar.financials import Financials

# Set EDGAR identity
set_identity("Curtis Gile curtis.j.gile@gmail.com")

# Placeholder values for DCF assumptions
WACC = 0.10  # Weighted Average Cost of Capital (10%)
growth_rate = 0.03  # Perpetual growth rate (3%)
projection_years = 20  # Number of years to project

# Get the latest 5 10-K filings for Apple
company = Company("AAPL")
ten_ks = company.get_filings(form="10-K").latest(5)

# Initialize lists to store the DataFrames for concatenation
balance_sheets_list = []
income_statements_list = []
cash_flows_list = []

# Function to standardize labels in DataFrames
def standardize_labels(df):
    df['label'] = df['label'].str.lower().str.strip()
    return df

# Loop through each 10-K filing to extract the financial statements for the filing year
for filing in ten_ks:
    try:
        # Extract the filing date to get the year
        filing_year = filing.filedate[:4]  # Extract the year part from the filing date

        # Directly access the financials attribute of the filing
        financials = filing.obj().financials
        
        # Extract the balance sheet, income statement, and cash flow statement as DataFrames
        bs_df = financials.get_balance_sheet().get_dataframe().reset_index()
        is_df = financials.get_income_statement().get_dataframe().reset_index()
        cf_df = financials.get_cash_flow_statement().get_dataframe().reset_index()

        # Standardize the labels in each DataFrame
        bs_df = standardize_labels(bs_df)
        is_df = standardize_labels(is_df)
        cf_df = standardize_labels(cf_df)
        
        # Keep only the columns for the specific filing year
        if filing_year in bs_df.columns:
            bs_df = bs_df[['label', filing_year]]
            balance_sheets_list.append(bs_df)
        if filing_year in is_df.columns:
            is_df = is_df[['label', filing_year]]
            income_statements_list.append(is_df)
        if filing_year in cf_df.columns:
            cf_df = cf_df[['label', filing_year]]
            cash_flows_list.append(cf_df)
    
    except Exception as e:
        print(f"Error processing a filing: {e}")
        continue

# Check if we have data to concatenate
if balance_sheets_list:
    balance_sheet_df_combined = pd.concat(balance_sheets_list, ignore_index=True)
else:
    balance_sheet_df_combined = pd.DataFrame()

if income_statements_list:
    income_statement_df_combined = pd.concat(income_statements_list, ignore_index=True)
else:
    income_statement_df_combined = pd.DataFrame()

if cash_flows_list:
    cash_flow_statement_df_combined = pd.concat(cash_flows_list, ignore_index=True)
else:
    cash_flow_statement_df_combined = pd.DataFrame()

# Set 'label' as the index for each DataFrame if they are not empty
if not balance_sheet_df_combined.empty:
    balance_sheet_df_combined.set_index('label', inplace=True)
if not income_statement_df_combined.empty:
    income_statement_df_combined.set_index('label', inplace=True)
if not cash_flow_statement_df_combined.empty:
    cash_flow_statement_df_combined.set_index('label', inplace=True)

# Debug: Print the combined DataFrames
print("\nCombined Balance Sheet DataFrame:")
print(balance_sheet_df_combined)

print("\nCombined Income Statement DataFrame:")
print(income_statement_df_combined)

print("\nCombined Cash Flow Statement DataFrame:")
print(cash_flow_statement_df_combined)

# Create a new DataFrame to store the output: Year, FCFF, NPV, and Terminal Value
output_df = pd.DataFrame(columns=['Year', 'Free Cash Flow to Firm', 'Net Present Value', 'Terminal Value'])

# Get the sorted list of unique years (columns) and process the latest 5 years
years_to_process = sorted([col for col in income_statement_df_combined.columns if col.isdigit()], reverse=True)[:5]

# Iterate over the years to calculate FCFF
for i in range(len(years_to_process) - 1):
    year = years_to_process[i]
    next_year = years_to_process[i + 1]
    
    try:
        # Debug: Print current year being processed
        print(f"\nProcessing year: {year}")

        # 1. Calculate EBIT (use Operating income)
        ebit = pd.to_numeric(income_statement_df_combined.at['operating income', year], errors='coerce') if 'operating income' in income_statement_df_combined.index else 0
        if pd.isna(ebit):
            print(f"EBIT not found for year {year}, setting to 0.")
            ebit = 0

        # 2. Calculate the effective tax rate
        income_before_tax = pd.to_numeric(income_statement_df_combined.at['income before provision for income taxes', year], errors='coerce') if 'income before provision for income taxes' in income_statement_df_combined.index else 0
        taxes = pd.to_numeric(income_statement_df_combined.at['provision for income taxes', year], errors='coerce') if 'provision for income taxes' in income_statement_df_combined.index else 0

        if income_before_tax == 0 or pd.isna(income_before_tax):
            print(f"Invalid income before tax for year {year}, setting tax rate to 0.")
            tax_rate = 0
        else:
            tax_rate = taxes / income_before_tax if not pd.isna(taxes) else 0

        # 3. Depreciation & Amortization (from Cash Flow Statement)
        depreciation = pd.to_numeric(cash_flow_statement_df_combined.at['depreciation and amortization', year], errors='coerce') if 'depreciation and amortization' in cash_flow_statement_df_combined.index else 0
        if pd.isna(depreciation):
            print(f"Depreciation not found for year {year}, setting to 0.")
            depreciation = 0

        # 4. Capital Expenditures (CapEx) (from Cash Flow Statement)
        capex = pd.to_numeric(cash_flow_statement_df_combined.at['payments for acquisition of property, plant and equipment', year], errors='coerce') if 'payments for acquisition of property, plant and equipment' in cash_flow_statement_df_combined.index else 0
        if pd.isna(capex):
            print(f"CapEx not found for year {year}, setting to 0.")
            capex = 0

        # 5. Change in Net Working Capital (NWC)
        def get_single_value(df, row_label, col_label):
            try:
                value = pd.to_numeric(df.at[row_label, col_label], errors='coerce')
                return value.item() if isinstance(value, pd.Series) else value
            except (KeyError, ValueError, IndexError):
                return 0  # Return 0 if there is any issue with extraction

        current_assets = sum([
            get_single_value(balance_sheet_df_combined, 'accounts receivable, net', year),
            get_single_value(balance_sheet_df_combined, 'inventories', year),
            get_single_value(balance_sheet_df_combined, 'other current assets', year)
        ])
        current_liabilities = sum([
            get_single_value(balance_sheet_df_combined, 'accounts payable', year),
            get_single_value(balance_sheet_df_combined, 'other current liabilities', year)
        ])

        next_current_assets = sum([
            get_single_value(balance_sheet_df_combined, 'accounts receivable, net', next_year),
            get_single_value(balance_sheet_df_combined, 'inventories', next_year),
            get_single_value(balance_sheet_df_combined, 'other current assets', next_year)
        ])
        next_current_liabilities = sum([
            get_single_value(balance_sheet_df_combined, 'accounts payable', next_year),
            get_single_value(balance_sheet_df_combined, 'other current liabilities', next_year)
        ])

        # Calculate change in NWC
        change_in_nwc = (next_current_assets - next_current_liabilities) - (current_assets - current_liabilities)

        # 6. Calculate FCFF and extract as scalar
        fcff = ebit * (1 - tax_rate) + depreciation - change_in_nwc - capex
        fcff = fcff.item() if isinstance(fcff, pd.Series) else fcff

        # Append FCFF to output DataFrame if it's a valid scalar
        if pd.notna(fcff):  
            output_df = pd.concat([output_df, pd.DataFrame({
                'Year': [year],
                'Free Cash Flow to Firm': [fcff / 1_000_000]  # Convert to millions
            })], ignore_index=True)

    except Exception as e:
        print(f"Error processing year {year}: {e}")
        continue

# Perform NPV and Terminal Value calculations for each year in the last 5 years
if not output_df.empty:
    for i, year in enumerate(output_df['Year']):
        latest_fcff = output_df.iloc[i]['Free Cash Flow to Firm']

        # Create a DataFrame for the DCF projections for this specific year
        projection_df = pd.DataFrame(index=range(1, projection_years + 1), columns=['Projected FCF', 'Discounted FCF'])

        # Project cash flows for the next 20 years using the growth rate
        for proj_year in projection_df.index:
            projected_fcf = latest_fcff * ((1 + growth_rate) ** proj_year)
            projection_df.at[proj_year, 'Projected FCF'] = projected_fcf

            # Discount the projected FCF to the present value
            discount_factor = (1 + WACC) ** proj_year
            discounted_fcf = projected_fcf / discount_factor
            projection_df.at[proj_year, 'Discounted FCF'] = discounted_fcf

        # Calculate the terminal value using the last year's projected FCF
        terminal_value = (projection_df.at[projection_years, 'Projected FCF'] * (1 + growth_rate)) / (WACC - growth_rate)

        # Discount the terminal value to present value
        terminal_discount_factor = (1 + WACC) ** projection_years
        present_value_terminal = terminal_value / terminal_discount_factor

        # Calculate Net Present Value (NPV) for this year
        npv = projection_df['Discounted FCF'].sum() + present_value_terminal

        # Update output DataFrame
        output_df.at[i, 'Net Present Value'] = npv
        output_df.at[i, 'Terminal Value'] = present_value_terminal

# Format the numbers in the output DataFrame to two decimal places
output_df[['Free Cash Flow to Firm', 'Net Present Value', 'Terminal Value']] = output_df[['Free Cash Flow to Firm', 'Net Present Value', 'Terminal Value']].applymap(lambda x: f"${x:,.2f}M" if pd.notna(x) else x)

# Output the updated DataFrame (now includes FCFF, NPV, and terminal value)
print(output_df)
