"""
Market data tools.

LangChain @tool definitions for fetching live and historical market data.

Planned tools:
  - get_current_price(ticker: str) -> dict
      Returns the latest quote for a given ticker symbol.

  - get_ohlcv(ticker: str, period: str, interval: str) -> list[dict]
      Returns OHLCV bars for the requested period and interval.

  - get_company_overview(ticker: str) -> dict
      Returns key company metadata (sector, market cap, exchange, etc.).

  - get_financial_statements(ticker: str, statement: str, period: str) -> dict
      Returns income statement, balance sheet, or cash-flow statement.
"""
