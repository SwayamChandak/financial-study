import { useState, useRef, useEffect } from 'react'

function Message({ text, role }) {
  return (
    <div className={`message ${role}`}>
      {text}
    </div>
  )
}

function QuizOverlay({ quiz, onClose, onSubmit }) {
  const [answers, setAnswers] = useState({})
  const [results, setResults] = useState(null)
  const [submitting, setSubmitting] = useState(false)
  const [quizState, setQuizState] = useState(quiz)
  const [retrying, setRetrying] = useState(false)

  function handleSelect(qId, option) {
    if (results) return
    setAnswers(prev => ({ ...prev, [qId]: option }))
  }

  async function handleSubmit() {
    if (submitting || results) return
    const unanswered = quizState.questions.filter(q => !answers[q.id])
    if (unanswered.length > 0) {
      alert(`Please answer all questions before submitting. (${unanswered.length} unanswered)`)
      return
    }
    setSubmitting(true)
    try {
      const res = await fetch('/api/quiz/submit', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ quiz_id: quizState.quiz_id, answers }),
      })
      if (!res.ok) {
        const err = await res.text()
        throw new Error(err || 'Submission failed')
      }
      const data = await res.json()
      setResults(data)
    } catch (err) {
      alert('Error: ' + err.message)
    } finally {
      setSubmitting(false)
    }
  }

  async function handleRetry() {
    setRetrying(true)
    setAnswers({})
    setResults(null)
    setSubmitting(false)
    try {
      const res = await fetch('/api/quiz/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count: 10 }),
      })
      if (!res.ok) {
        const err = await res.text()
        throw new Error(err || 'Generation failed')
      }
      const data = await res.json()
      setQuizState(data)
    } catch (err) {
      alert('Error: ' + err.message)
    } finally {
      setRetrying(false)
    }
  }

  if (!quizState) return null

  return (
    <div className="quiz-backdrop" onClick={onClose}>
      <div className="quiz-overlay" onClick={e => e.stopPropagation()}>
        <div className="quiz-header">
          <h2>Knowledge Quiz</h2>
          <span className="quiz-count">{quizState.total_questions} Questions</span>
          <button className="quiz-close" onClick={onClose}>&times;</button>
        </div>

        {results && (
          <div className="quiz-score-bar">
            <span className={`score-label ${results.percentage >= 60 ? 'pass' : 'fail'}`}>
              Score: {results.score} ({results.percentage}%)
            </span>
            <button className="teach-btn quiz-retry-btn" onClick={handleRetry}>
              Retry Quiz
            </button>
          </div>
        )}

        <div className="quiz-body">
          {quizState.questions.map(q => {
            const result = results?.results?.find(r => r.question_id === String(q.id))
            const selected = answers[q.id]
            return (
              <div key={q.id} className={`quiz-question ${result ? 'reviewed' : ''}`}>
                <p className="q-text">{q.id}. {q.question}</p>
                <div className="q-options">
                  {Object.entries(q.options).map(([key, val]) => {
                    const isSelected = selected === key
                    const isCorrect = result && result.correct_answer === key
                    const isWrong = result && isSelected && result.user_answer === key && !result.is_correct
                    let cls = 'q-option'
                    if (isSelected && !result) cls += ' selected'
                    if (result) {
                      if (isCorrect) cls += ' correct'
                      if (isWrong) cls += ' wrong'
                    }
                    return (
                      <label key={key} className={cls} onClick={() => handleSelect(q.id, key)}>
                        <span className="q-checkbox">
                          {result
                            ? (isCorrect ? '✓' : isWrong ? '✗' : '')
                            : (isSelected ? '✓' : '')
                          }
                        </span>
                        <span className="q-option-letter">{key}.</span>
                        <span className="q-option-text">{val}</span>
                      </label>
                    )
                  })}
                </div>
                {result && !result.is_correct && (
                  <div className="q-feedback">
                    <p><strong>Correct answer:</strong> {result.correct_answer}</p>
                    <p><strong>Explanation:</strong> {result.explanation}</p>
                    {result.source && (
                      <p className="q-source">Source: {result.source}</p>
                    )}
                  </div>
                )}
                {result && result.is_correct && (
                  <div className="q-feedback correct-feedback">
                    <p className="q-source">Source: {result.source}</p>
                  </div>
                )}
              </div>
            )
          })}
        </div>

        <div className="quiz-footer">
          {!results ? (
            <button
              className="teach-btn quiz-submit-btn"
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? 'Submitting...' : 'Submit Answers'}
            </button>
          ) : (
            <button className="teach-btn quiz-close-btn" onClick={onClose}>
              Close
            </button>
          )}
        </div>
      </div>
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
  const [quizLoading, setQuizLoading] = useState(false)
  const [quizData, setQuizData] = useState(null)
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

  async function handleTakeQuiz() {
    if (quizLoading) return
    setQuizLoading(true)
    try {
      const res = await fetch('/api/quiz/generate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ count: 10 }),
      })
      if (!res.ok) {
        const err = await res.json()
        throw new Error(err.error || `Request failed (${res.status})`)
      }
      const data = await res.json()
      setQuizData(data)
    } catch (err) {
      alert('Error: ' + err.message)
    } finally {
      setQuizLoading(false)
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
        <button
          className="teach-btn quiz-btn"
          onClick={handleTakeQuiz}
          disabled={quizLoading}
        >
          {quizLoading ? 'Generating...' : 'Take Quiz'}
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

      {quizData && (
        <QuizOverlay
          quiz={quizData}
          onClose={() => { setQuizData(null) }}
        />
      )}
    </>
  )
}

export default App
