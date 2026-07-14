import { useState, useRef, useEffect } from 'react'

function Message({ text, role }) {
  return (
    <div className={`message ${role}`}>
      {text}
    </div>
  )
}

function App() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  async function sendQuery() {
    const query = input.trim()
    if (!query || loading) return

    setInput('')
    setLoading(true)
    setMessages(prev => [...prev, { text: query, role: 'user' }])

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ query }),
      })

      if (!res.ok) {
        const errText = await res.text()
        throw new Error(errText || `Request failed (${res.status})`)
      }

      const data = await res.json()
      setMessages(prev => [...prev, { text: data.response, role: 'bot' }])
    } catch (err) {
      setMessages(prev => [...prev, { text: 'Error: ' + err.message, role: 'error' }])
    } finally {
      setLoading(false)
    }
  }

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendQuery()
    }
  }

  return (
    <>
      <header>
        <div className="dot" />
        <h1>Financial Study</h1>
        <span className="subtitle">— Chatbot</span>
      </header>

      <div id="chat-container">
        {messages.length === 0 && (
          <div className="empty-state">
            Ask a question about financial markets to get started.
          </div>
        )}
        {messages.map((msg, i) => (
          <Message key={i} text={msg.text} role={msg.role} />
        ))}
        {loading && (
          <div className="message bot loading">Thinking...</div>
        )}
        <div ref={endRef} />
      </div>

      <div id="input-area">
        <input
          type="text"
          id="query-input"
          placeholder="Ask about financial markets, stocks, economics..."
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          autoFocus
        />
        <button id="send-btn" onClick={sendQuery} disabled={loading || !input.trim()}>
          Send
        </button>
      </div>
    </>
  )
}

export default App
