"""
Financial statements tools.

LangChain @tool definitions for fetching and parsing structured
financial statement data.

Planned tools:
  - get_income_statement(ticker: str, period: str) -> dict
      Returns revenue, gross profit, operating income, net income, EPS, etc.

  - get_balance_sheet(ticker: str, period: str) -> dict
      Returns assets, liabilities, equity, debt levels, etc.

  - get_cash_flow_statement(ticker: str, period: str) -> dict
      Returns operating / investing / financing cash flows, free cash flow.

  - get_key_ratios(ticker: str) -> dict
      Returns P/E, P/B, EV/EBITDA, ROE, ROA, debt-to-equity, etc.
"""
