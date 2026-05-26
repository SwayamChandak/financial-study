"""
Entry point for the financial studying agent system built on LangGraph.

Two workflows are exposed from here:

  1. Daily Article Workflow
     - Triggered on a schedule (e.g. cron / APScheduler)
     - Retrieves study content from the RAG store by module number and
       chapter number
     - Refines the retrieved content into a concise article
     - Delivers the article to the user via the Telegram bot

  2. Chatbot Q&A Workflow
     - Triggered by an incoming Telegram message from the user
     - Accepts a free-text question about previously delivered content
     - Queries the vector DB to retrieve the most relevant stored passages
     - Generates a grounded answer and replies through the Telegram bot

Steps to implement:
  1. Load settings (config.settings)
  2. Build both compiled graphs (graph.builder)
  3. Start the Telegram bot listener (handles chatbot workflow triggers)
  4. Register the scheduler job (handles daily article workflow triggers)
  5. Run the event loop
"""
