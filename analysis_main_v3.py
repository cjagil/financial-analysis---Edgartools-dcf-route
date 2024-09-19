import pandas as pd
from edgar import *
from edgar.financials import Financials

# Set EDGAR identity
set_identity("Curtis Gile curtis.j.gile@gmail.com")

# Placeholder values for DCF assumptions
WACC = 0.10  # Weighted Average Cost of Capital (10%)
growth_rate = 0.03  # Perpetual growth rate (3%)
projection_years = 20  # Number of years to project

# Prompt the user to input the ticker symbol
ticker_symbol = input("Please enter the ticker symbol for the company: ").strip().upper()

# Get the latest 10-K filing for the specified company
company = Company(ticker_symbol)
latest_10k = company.get_filings(form="10-K").latest(1)

# Initialize empty DataFrames to store data
balance_sheet_df = pd.DataFrame()
income_statement_df = pd.DataFrame()
cash_flow_statement_df = pd.DataFrame()

try:
    # Get the financials object
    financials = latest_10k.obj().financials

    # Extract data and assign to DataFrames
    balance_sheet_df = financials.get_balance_sheet().get_dataframe()
    income_statement_df = financials.get_income_statement().get_dataframe()
    cash_flow_statement_df = financials.get_cash_flow_statement().get_dataframe()

except Exception as e:
    print(f"Error processing the filing: {e}")

# Define possible label variations for each item
label_variations = {
    'ebit': ['Operating income', 'Operating profit', 'Income from operations'],
    'income_before_tax': ['Income before provision for income taxes', 'Income before tax', 'Earnings before income taxes'],
    'taxes': ['Provision for income taxes', 'Income taxes', 'Taxes'],
    'depreciation': ['Depreciation and amortization', 'Depreciation'],
    'capex': ['Payments for acquisition of property, plant and equipment', 'Capital expenditures', 'CapEx'],
    'accounts_receivable': ['Accounts receivable, net', 'Receivables, net'],
    'inventories': ['Inventories', 'Inventory'],
    'other_current_assets': ['Other current assets'],
    'accounts_payable': ['Accounts payable'],
    'other_current_liabilities': ['Other current liabilities', 'Accrued liabilities']
}

# Helper function to find the correct label in the DataFrame
def get_financial_value(df, possible_labels, year):
    for label in possible_labels:
        try:
            value = pd.to_numeric(df.at[label, year], errors='coerce')
            if pd.notna(value):
                return value.item() if isinstance(value, pd.Series) else value
        except KeyError:
            continue
    return 0  # Return 0 if no valid label is found

# Create a new DataFrame to store the output: Year, FCFF, NPV, and Terminal Value
output_df = pd.DataFrame(columns=['Year', 'Free Cash Flow to Firm', 'Net Present Value', 'Terminal Value'])

# Iterate over all years except the last one to ensure there's a "next year" for ΔNWC
for i in range(len(income_statement_df.columns) - 1):
    year = income_statement_df.columns[i]
    next_year = income_statement_df.columns[i + 1]

    try:
        # 1. Calculate EBIT
        ebit = get_financial_value(income_statement_df, label_variations['ebit'], year)

        # 2. Calculate the effective tax rate
        income_before_tax = get_financial_value(income_statement_df, label_variations['income_before_tax'], year)
        taxes = get_financial_value(income_statement_df, label_variations['taxes'], year)

        # Calculate the tax rate
        tax_rate = taxes / income_before_tax if income_before_tax != 0 else 0

        # 3. Depreciation & Amortization
        depreciation = get_financial_value(cash_flow_statement_df, label_variations['depreciation'], year)

        # 4. Capital Expenditures (CapEx)
        capex = get_financial_value(cash_flow_statement_df, label_variations['capex'], year)

        # 5. Change in Net Working Capital (NWC)
        current_assets = sum([
            get_financial_value(balance_sheet_df, label_variations['accounts_receivable'], year),
            get_financial_value(balance_sheet_df, label_variations['inventories'], year),
            get_financial_value(balance_sheet_df, label_variations['other_current_assets'], year)
        ])
        current_liabilities = sum([
            get_financial_value(balance_sheet_df, label_variations['accounts_payable'], year),
            get_financial_value(balance_sheet_df, label_variations['other_current_liabilities'], year)
        ])

        next_current_assets = sum([
            get_financial_value(balance_sheet_df, label_variations['accounts_receivable'], next_year),
            get_financial_value(balance_sheet_df, label_variations['inventories'], next_year),
            get_financial_value(balance_sheet_df, label_variations['other_current_assets'], next_year)
        ])
        next_current_liabilities = sum([
            get_financial_value(balance_sheet_df, label_variations['accounts_payable'], next_year),
            get_financial_value(balance_sheet_df, label_variations['other_current_liabilities'], next_year)
        ])

        # Calculate change in NWC
        change_in_nwc = (next_current_assets - next_current_liabilities) - (current_assets - current_liabilities)

        # 6. Calculate FCFF
        fcff = ebit * (1 - tax_rate) + depreciation - change_in_nwc - capex

        # Append FCFF to output DataFrame if it's a valid scalar
        if pd.notna(fcff):
            output_df = pd.concat([output_df, pd.DataFrame({
                'Year': [year],
                'Free Cash Flow to Firm': [fcff / 1_000_000]  # Convert to millions
            })], ignore_index=True)

    except KeyError:
        continue

# Perform the rest of the DCF calculations...


# Check if the output_df is not empty before proceeding
if not output_df.empty:
    # Perform NPV and Terminal Value calculations for each year
    for i, year in enumerate(output_df['Year']):
        latest_fcff = output_df.iloc[i]['Free Cash Flow to Firm']

        # Create a DataFrame for the DCF projections for this specific year
        projection_df = pd.DataFrame(index=range(1, projection_years + 1), columns=['Projected FCF', 'Discounted FCF'])

        # Project cash flows for the next 20 years using the growth rate
        for proj_year in projection_df.index:
            # Calculate projected FCF for each year
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
