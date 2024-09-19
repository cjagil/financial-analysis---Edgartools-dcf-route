import pandas as pd
from edgar import *
from edgar.financials import Financials

# Open a text file to write debug output
debug_file = open('debug_output.txt', 'w')

# Set EDGAR identity
set_identity("Curtis Gile curtis.j.gile@gmail.com")

# Placeholder values for DCF assumptions
WACC = 0.10  # Weighted Average Cost of Capital (10%)
growth_rate = 0.03  # Perpetual growth rate (3%)
projection_years = 20  # Number of years to project

# Prompt the user to input the ticker symbol
ticker_symbol = input("Please enter the ticker symbol for the company: ").strip().upper()

combined_data = pd.DataFrame()  # Initialize an empty DataFrame

# Define possible label variations for each item
label_variations = {
    'accounts_receivable': [
        'Accounts receivable, net', 'Receivables, net', 'Accounts receivable',
        'Accounts Receivable', 'Trade receivables', 'Vendor non-trade receivables',
        'Accounts receivable net', 'Trade and other receivables', 'Customer receivables'
    ],
    'inventories': [
        'Inventories', 'Inventory', 'Inventories, net', 'Stock', 'Finished goods',
        'Inventory, net', 'Merchandise inventory', 'Raw materials'
    ],
    'other_current_assets': [
        'Other current assets', 'Other current and non-current assets',
        'Prepaid expenses', 'Deferred charges', 'Other assets', 'Current assets, other'
    ],
    'accounts_payable': [
        'Accounts payable', 'Payables', 'Trade payables',
        'Accounts payable and accrued liabilities', 'Trade and other payables',
        'Accounts payable net', 'Suppliers and other payables'
    ],
    'other_current_liabilities': [
        'Other current liabilities', 'Accrued liabilities', 'Accrued expenses',
        'Other current and non-current liabilities', 'Short-term borrowings',
        'Current liabilities, other', 'Other short-term liabilities', 'Accrued liabilities and other'
    ],
    'ebit': [
        'Operating income', 'Operating profit', 'Income from operations',
        'Earnings Before Interest and Taxes', 'EBIT', 'Operating earnings',
        'Operating profit/loss'
    ],
    'income_before_tax': [
        'Income before provision for income taxes', 'Income before tax',
        'Earnings before income taxes', 'Pretax income', 'Income before taxes',
        'Income before tax expense', 'Earnings before taxes', 'Profit before tax'
    ],
    'taxes': [
        'Provision for income taxes', 'Income taxes', 'Taxes',
        'Income tax expense', 'Provision for taxes', 'Tax provision',
        'Tax expense', 'Taxes payable'
    ],
    'depreciation': [
        'Depreciation and amortization', 'Depreciation',
        'Depreciation expense', 'Amortization of intangibles',
        'Depreciation and amortization expense', 'Amortization'
    ],
    'capex': [
        'Payments for acquisition of property, plant and equipment',
        'Capital expenditures', 
        'CapEx', 
        'Property, plant, and equipment additions',
        'Purchases of property and equipment',
        'Investment in property and equipment',
        'Additions to property, plant, and equipment',
        'Property and equipment expenditures'
    ]
}

# Function to update a financial key with a new value if conditions are met
def update_financial_value(financial_dict, key, new_value, year):
    current_value = financial_dict.get(key, 0)
    
    # Log the current and new values
    debug_file.write(f"Year: {year}, Key: {key}, Current Value: {current_value}, New Value: {new_value}\n")
    
    # Only update if the new value is greater than the current value
    if current_value == 0 or new_value > current_value:
        financial_dict[key] = new_value
        debug_file.write(f"Updated Year: {year}, Key: {key} with New Value: {new_value}\n")
    else:
        debug_file.write(f"Retained Year: {year}, Key: {key} with Current Value: {current_value}\n")

# Function to get financial values, modified to retain the highest valid value found
def get_financial_value(df, possible_labels, year):
    # Initialize extracted_value as None
    extracted_value = None

    # Debug: Write available labels in the DataFrame to the debug file
    debug_file.write(f"\nLooking for labels in DataFrame for year {year}. Available labels:\n")
    debug_file.write(f"{df.index.tolist()}\n")

    for label in possible_labels:
        try:
            # Debug: Check if we're searching for the right label
            debug_file.write(f"Trying to find label '{label}' in the DataFrame for year {year}.\n")

            # Attempt to get the value from the DataFrame
            value = pd.to_numeric(df.at[label, year], errors='coerce')
            if pd.notna(value):
                # Debug: Found a potential value for the label
                debug_file.write(f"Found value for '{label}': {value}\n")

                # Only overwrite if extracted_value is None or the new value is greater
                if extracted_value is None or value > extracted_value:
                    extracted_value = value
                    debug_file.write(f"Updating value with '{label}': {extracted_value}\n")

        except KeyError:
            debug_file.write(f"Label '{label}' not found in DataFrame for year {year}.\n")
            continue

    # Debug: If no valid label was found, return 0
    if extracted_value is None:
        debug_file.write(f"No matching labels found for year {year}. Retaining previous value or setting to 0.\n")
        extracted_value = 0

    debug_file.write(f"Year: {year}, Key: {possible_labels[0]}, Extracted Value: {extracted_value}\n")
    return extracted_value

# Main data extraction loop
try:
    # Get the latest 3 10-K filings
    filings = Company(ticker_symbol).get_filings(form="10-K").latest(3)

    # Iterate through each filing to extract financial data
    for filing in filings:
        financials = filing.obj().financials
        balance_sheet_df = financials.get_balance_sheet().get_dataframe()
        income_statement_df = financials.get_income_statement().get_dataframe()
        cash_flow_statement_df = financials.get_cash_flow_statement().get_dataframe()

        # Extract relevant financial data for the primary labels
        years = income_statement_df.columns.tolist()
        for year in years:
            data = {}
            for key, labels in label_variations.items():
                if key in ['ebit', 'income_before_tax', 'taxes']:
                    extracted_value = get_financial_value(income_statement_df, labels, year)
                elif key in ['depreciation', 'capex']:
                    extracted_value = get_financial_value(cash_flow_statement_df, labels, year)
                else:
                    extracted_value = get_financial_value(balance_sheet_df, labels, year)

                # Use the update function to store the value
                update_financial_value(data, key, extracted_value, year)

            # Add the 'Year' key to the data
            data['Year'] = year

            # Debug: Print data before adding to combined_data
            debug_file.write(f"Data to be added for year {year}: {data}\n")

            combined_data = pd.concat([combined_data, pd.DataFrame([data])], ignore_index=True)

    # Remove duplicate years
    combined_data.drop_duplicates(subset=['Year'], inplace=True)

    # Debug: Output the contents of combined_data before FCFF calculations
    debug_file.write("\nContents of combined_data before FCFF calculation:\n")
    debug_file.write(combined_data.to_string() + "\n")
    

except Exception as e:
    debug_file.write(f"Error processing the filings: {e}\n")

# Output the combined DataFrame to the debug file
debug_file.write("\nCombined DataFrame:\n")
debug_file.write(combined_data.to_string() + "\n")

# Create a new DataFrame to store the DCF output
output_df = pd.DataFrame(columns=['Year', 'Free Cash Flow to Firm', 'Net Present Value', 'Terminal Value'])

# Iterate over all years in the combined data
years = combined_data['Year'].tolist()
for i in range(len(years) - 1):
    year = years[i]
    next_year = years[i + 1]

    try:
        # 1. Calculate EBIT
        ebit = get_financial_value(combined_data, label_variations['ebit'], year)
        debug_file.write(f"Year: {year}, EBIT: {ebit}\n")  # Debug statement

        # 2. Calculate the effective tax rate
        income_before_tax = get_financial_value(combined_data, label_variations['income_before_tax'], year)
        taxes = get_financial_value(combined_data, label_variations['taxes'], year)
        debug_file.write(f"Year: {year}, Income Before Tax: {income_before_tax}, Taxes: {taxes}\n")  # Debug statement

        # Calculate the tax rate
        tax_rate = taxes / income_before_tax if income_before_tax != 0 else 0

        # 3. Depreciation & Amortization
        depreciation = get_financial_value(combined_data, label_variations['depreciation'], year)
        debug_file.write(f"Year: {year}, Depreciation: {depreciation}\n")  # Debug statement

        # 4. Capital Expenditures (CapEx)
        capex = get_financial_value(combined_data, label_variations['capex'], year)
        debug_file.write(f"Year: {year}, CapEx: {capex}\n")  # Debug statement

        # 5. Change in Net Working Capital (NWC)
        current_assets = sum([
            get_financial_value(combined_data, label_variations['accounts_receivable'], year),
            get_financial_value(combined_data, label_variations['inventories'], year),
            get_financial_value(combined_data, label_variations['other_current_assets'], year)
        ])
        current_liabilities = sum([
            get_financial_value(combined_data, label_variations['accounts_payable'], year),
            get_financial_value(combined_data, label_variations['other_current_liabilities'], year)
        ])
        next_current_assets = sum([
            get_financial_value(combined_data, label_variations['accounts_receivable'], next_year),
            get_financial_value(combined_data, label_variations['inventories'], next_year),
            get_financial_value(combined_data, label_variations['other_current_assets'], next_year)
        ])
        next_current_liabilities = sum([
            get_financial_value(combined_data, label_variations['accounts_payable'], next_year),
            get_financial_value(combined_data, label_variations['other_current_liabilities'], next_year)
        ])

        # Calculate change in NWC
        change_in_nwc = (next_current_assets - next_current_liabilities) - (current_assets - current_liabilities)
        debug_file.write(f"Year: {year}, Change in NWC: {change_in_nwc}\n")  # Debug statement

        # 6. Calculate FCFF
        # Validate if all necessary values are present before calculating FCFF
        if ebit is not None and tax_rate is not None and depreciation is not None and capex is not None:
            fcff = ebit * (1 - tax_rate) + depreciation - change_in_nwc - capex
            # Ensure the FCFF value is numeric and scaled correctly
            fcff = float(fcff) / 1_000_000  # Convert to millions if necessary
        else:
            fcff = 0
        
        debug_file.write(f"Year: {year}, FCFF: {fcff}\n")  # Debug statement

        # Append FCFF to output DataFrame if it's a valid scalar
        if pd.notna(fcff):
            output_df = pd.concat([output_df, pd.DataFrame({
                'Year': [year],
                'Free Cash Flow to Firm': [fcff]
            })], ignore_index=True)

    except KeyError as e:
        debug_file.write(f"Error in processing year {year}: {e}\n")  # Debug statement
        continue

# Perform NPV and Terminal Value calculations on the combined data
if not output_df.empty:
    for i, year in enumerate(output_df['Year']):
        latest_fcff = output_df.iloc[i]['Free Cash Flow to Firm']
        projection_df = pd.DataFrame(index=range(1, projection_years + 1), columns=['Projected FCF', 'Discounted FCF'])

        # Project cash flows
        for proj_year in projection_df.index:
            projected_fcf = latest_fcff * ((1 + growth_rate) ** proj_year)
            projection_df.at[proj_year, 'Projected FCF'] = projected_fcf
            discount_factor = (1 + WACC) ** proj_year
            discounted_fcf = projected_fcf / discount_factor
            projection_df.at[proj_year, 'Discounted FCF'] = discounted_fcf

        # Calculate terminal value
        terminal_value = (projection_df.at[projection_years, 'Projected FCF'] * (1 + growth_rate)) / (WACC - growth_rate)
        terminal_discount_factor = (1 + WACC) ** projection_years
        present_value_terminal = terminal_value / terminal_discount_factor

        # Calculate NPV
        npv = projection_df['Discounted FCF'].sum() + present_value_terminal

        # Update output DataFrame
        output_df.at[i, 'Net Present Value'] = npv
        output_df.at[i, 'Terminal Value'] = present_value_terminal

# Format the numbers in the output DataFrame to two decimal places
# Debug: Output the DataFrame after FCFF calculation
debug_file.write("\nOutput DataFrame after FCFF calculation:\n")
debug_file.write(output_df.to_string() + "\n")

output_df[['Free Cash Flow to Firm', 'Net Present Value', 'Terminal Value']] = output_df[['Free Cash Flow to Firm', 'Net Present Value', 'Terminal Value']].applymap(lambda x: f"${x:,.2f}M" if pd.notna(x) else x)

# Output the updated DataFrame (now includes FCFF, NPV, and terminal value)
print(output_df)
debug_file.write("\nFinal Output DataFrame:\n")
debug_file.write(output_df.to_string() + "\n")

# Close the debug file
debug_file.close()
