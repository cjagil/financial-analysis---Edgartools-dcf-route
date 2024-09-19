import pandas as pd
from edgar import *
from edgar.financials import Financials

# Set EDGAR identity
set_identity("Curtis Gile curtis.j.gile@gmail.com")

# Get the latest three 10-K filings
filings = Company("AAPL").get_filings(form="10-K").latest(5)

# Access the most recent 10-K filing
tenk1 = filings[0].obj()
financials1 = tenk1.financials
balance_sheet1 = financials1.get_balance_sheet().get_dataframe()
print(balance_sheet1)

# Access the 10-K filing two years removed
tenk2 = filings[1].obj()
financials2 = tenk2.financials
balance_sheet2 = financials2.get_balance_sheet().get_dataframe()
print(balance_sheet2)

tenk3 = filings[2].obj()
financials3 = tenk3.financials
balance_sheet3 = financials1.get_balance_sheet().get_dataframe()
print(balance_sheet3)

# Access the 10-K filing two years removed
tenk3 = filings[3].obj()
financials3 = tenk2.financials
balance_sheet3 = financials2.get_balance_sheet().get_dataframe()
print(balance_sheet3)
