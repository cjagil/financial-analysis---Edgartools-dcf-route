import pandas as pd
from edgar import *
from edgar.financials import Financials

# Set EDGAR identity
set_identity("Curtis Gile curtis.j.gile@gmail.com")

# Placeholder values for DCF assumptions
WACC = 0.10  # Weighted Average Cost of Capital (10%)
growth_rate = 0.03  # Perpetual growth rate (3%)
projection_years = 20  # Number of years to project

# Get the last 10 10-K filings for Apple
company = Company("AAPL")
ten_ks = company.get_filings(form="10-K").latest(2)

# Initialize empty DataFrames to combine data
balance_sheet_df = pd.DataFrame()
income_statement_df = pd.DataFrame()
cash_flow_statement_df = pd.DataFrame()

# Extract financial data from each 10-K filing
for filing in ten_ks:
    try:
        # Get the financials object
        financials = filing.obj().financials
        
        # Extract data from the filing and concatenate to the main DataFrames
        balance_sheet_df = pd.concat([balance_sheet_df, financials.get_balance_sheet().get_dataframe()])
        income_statement_df = pd.concat([income_statement_df, financials.get_income_statement().get_dataframe()])
        cash_flow_statement_df = pd.concat([cash_flow_statement_df, financials.get_cash_flow_statement().get_dataframe()])
    
    except Exception as e:
        print(f"Error processing filing: {e}")
        continue

# Remove duplicate years to ensure unique data
balance_sheet_df = balance_sheet_df.loc[:, ~balance_sheet_df.columns.duplicated()]
income_statement_df = income_statement_df.loc[:, ~income_statement_df.columns.duplicated()]
cash_flow_statement_df = cash_flow_statement_df.loc[:, ~cash_flow_statement_df.columns.duplicated()]

# Create a new DataFrame to store the output: Year, FCFF, NPV, and Terminal Value
output_df = pd.DataFrame(columns=['Year', 'Free Cash Flow to Firm', 'Net Present Value', 'Terminal Value'])

# Iterate over all years except the last one to ensure there's a "next year" for ΔNWC
for i in range(len(income_statement_df.columns) - 1):
    year = income_statement_df.columns[i]
    next_year = income_statement_df.columns[i + 1]
    
    try:
        # 1. Calculate EBIT (use Operating income)
        ebit = pd.to_numeric(income_statement_df.at['Operating income', year], errors='coerce')
        ebit = ebit.iloc[0] if isinstance(ebit, pd.Series) else ebit

        # 2. Calculate the effective tax rate
        income_before_tax = pd.to_numeric(income_statement_df.at['Income before provision for income taxes', year], errors='coerce')
        taxes = pd.to_numeric(income_statement_df.at['Provision for income taxes', year], errors='coerce')

        # Ensure scalar extraction to avoid ambiguous truth value errors
        income_before_tax = income_before_tax.iloc[0] if isinstance(income_before_tax, pd.Series) else income_before_tax
        taxes = taxes.iloc[0] if isinstance(taxes, pd.Series) else taxes

        # Calculate the tax rate
        tax_rate = taxes / income_before_tax if income_before_tax != 0 else 0

        # 3. Depreciation & Amortization (from Cash Flow Statement)
        depreciation = pd.to_numeric(cash_flow_statement_df.at['Depreciation and amortization', year], errors='coerce')
        depreciation = depreciation.iloc[0] if isinstance(depreciation, pd.Series) else depreciation

        # 4. Capital Expenditures (CapEx) (from Cash Flow Statement)
        capex = pd.to_numeric(cash_flow_statement_df.at['Payments for acquisition of property, plant and equipment', year], errors='coerce')
        capex = capex.iloc[0] if isinstance(capex, pd.Series) else capex

        # 5. Change in Net Working Capital (NWC)
        def get_single_value(df, row_label, col_label):
            try:
                value = pd.to_numeric(df.at[row_label, col_label], errors='coerce')
                return value.item() if isinstance(value, pd.Series) else value
            except (KeyError, ValueError, IndexError):
                return 0  # Return 0 if there is any issue with extraction

        current_assets = sum([
            get_single_value(balance_sheet_df, 'Accounts receivable, net', year),
            get_single_value(balance_sheet_df, 'Inventories', year),
            get_single_value(balance_sheet_df, 'Other current assets', year)
        ])
        current_liabilities = sum([
            get_single_value(balance_sheet_df, 'Accounts payable', year),
            get_single_value(balance_sheet_df, 'Other current liabilities', year)
        ])

        next_current_assets = sum([
            get_single_value(balance_sheet_df, 'Accounts receivable, net', next_year),
            get_single_value(balance_sheet_df, 'Inventories', next_year),
            get_single_value(balance_sheet_df, 'Other current assets', next_year)
        ])
        next_current_liabilities = sum([
            get_single_value(balance_sheet_df, 'Accounts payable', next_year),
            get_single_value(balance_sheet_df, 'Other current liabilities', next_year)
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


    except KeyError:
        # Skip if any data is missing
        continue

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
