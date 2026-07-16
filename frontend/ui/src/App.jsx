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
  const [teachLoading, setTeachLoading] = useState(false)
  const [currentPos, setCurrentPos] = useState(null)
  const [teachDone, setTeachDone] = useState(false)
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

  async function handleTeach(action) {
    if (teachLoading) return
    setTeachLoading(true)

    try {
      const endpoint = action === 'start' ? '/api/teach/start' : '/api/teach/next'
      const res = await fetch(endpoint, { method: 'POST' })

      if (!res.ok) {
        const errText = await res.text()
        throw new Error(errText || `Request failed (${res.status})`)
      }

      const data = await res.json()

      if (action === 'start') {
        setMessages([{
          text: `**Teaching Mode — Module ${data.module}, Chapter ${data.chapter}**\n\n${data.summary}`,
          role: 'bot',
        }])
      } else {
        setMessages(prev => [...prev, {
          text: `**Module ${data.module}, Chapter ${data.chapter}**\n\n${data.summary}`,
          role: 'bot',
        }])
      }

      setCurrentPos({ module: data.module, chapter: data.chapter })
      setTeachDone(data.done)
    } catch (err) {
      setMessages(prev => [...prev, { text: 'Error: ' + err.message, role: 'error' }])
    } finally {
      setTeachLoading(false)
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

      <div id="teach-bar">
        <button
          className="teach-btn restart"
          onClick={() => handleTeach('start')}
          disabled={teachLoading}
        >
          Restart Teaching
        </button>
        <button
          className="teach-btn next"
          onClick={() => handleTeach('next')}
          disabled={teachLoading || teachDone}
        >
          {teachLoading ? 'Loading...' : 'Next Chapter'}
        </button>
        {currentPos && (
          <span id="teach-pos">
            Module {currentPos.module}, Chapter {currentPos.chapter}
            {teachDone && ' — All done!'}
          </span>
        )}
      </div>

      <div id="chat-container">
        {messages.length === 0 && (
          <div className="empty-state">
            Ask a question or use the teaching buttons above to read chapter summaries.
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
