"""
News search tools.

LangChain @tool definitions for retrieving financial news and sentiment.

Planned tools:
  - search_news(query: str, max_results: int) -> list[dict]
      Returns recent news articles matching the query.

  - get_ticker_news(ticker: str, days: int) -> list[dict]
      Returns recent news articles specifically about a ticker.

  - get_earnings_calendar(start_date: str, end_date: str) -> list[dict]
      Returns upcoming earnings release dates for tracked tickers.
"""
