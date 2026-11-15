import { useEffect, useRef, useState } from 'react'

export async function llmRequest(path, options = {}) {
  const res = await fetch(`/api/llm/${path}`, options)
  const data = await res.json()
  if (!res.ok) {
    throw new Error(data.error || data.detail || `Request failed (${res.status})`)
  }
  return data
}

export default function LLMSettings({ onClose, onChange }) {
  const dialog = useRef(null)
  const [providers, setProviders] = useState([])
  const [saved, setSaved] = useState(null)
  const [form, setForm] = useState({ provider: 'ollama', model: 'llama3.2' })
  const [apiKey, setApiKey] = useState('')
  const [busy, setBusy] = useState(true)
  const [error, setError] = useState('')
  const [status, setStatus] = useState('')

  useEffect(() => {
    dialog.current.showModal()
    let active = true
    Promise.all([llmRequest('providers'), llmRequest('config')])
      .then(([metadata, config]) => {
        if (!active) return
        setProviders(metadata)
        setSaved(config)
        setForm(config.selection || {
          provider: 'ollama', model: 'llama3.2',
          base_url: config.defaults.ollama_base_url,
        })
        onChange(config)
      })
      .catch(err => { if (active) setError(err.message) })
      .finally(() => { if (active) setBusy(false) })
    return () => { active = false }
  }, [onChange])

  const spec = providers.find(p => p.id === form.provider)
  const keepsKey = saved?.has_key && saved.selection?.provider === form.provider

  function chooseProvider(provider) {
    const next = providers.find(p => p.id === provider)
    setForm({
      provider, model: next.models[0] || '',
      ...(provider === 'ollama' ? { base_url: saved?.defaults?.ollama_base_url || '' } : {}),
    })
    setApiKey('')
    setError('')
    setStatus('')
  }

  function setField(name, value) {
    setForm(prev => ({ ...prev, [name]: value }))
    setStatus('')
  }

  async function act(action) {
    setBusy(true)
    setError('')
    setStatus('')
    try {
      if (action === 'clear') {
        await llmRequest('config', { method: 'DELETE' })
        const config = await llmRequest('config')
        setSaved(config)
        onChange(config)
        setApiKey('')
        setForm({
          provider: 'ollama', model: 'llama3.2',
          base_url: config.defaults.ollama_base_url,
        })
        setStatus('Selection cleared. Environment defaults are active.')
        return
      }
      const payload = {
        ...form,
        api_key: apiKey || null,
        base_url: form.base_url || null,
        endpoint: form.endpoint || null,
        api_version: form.api_version || null,
        deployment: form.deployment || null,
      }
      const result = await llmRequest(action === 'test' ? 'test' : 'config', {
        method: action === 'test' ? 'POST' : 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      })
      if (action === 'test') {
        setStatus(`Connection successful (${result.latency_ms} ms). Not saved.`)
      } else {
        const config = await llmRequest('config')
        setSaved(config)
        onChange(config)
        setApiKey('')
        setStatus(`Saved for ${Math.round(config.ttl_seconds / 3600)} hours. Applies to chat, quizzes and study.`)
      }
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <dialog
      ref={dialog}
      className="llm-settings"
      aria-labelledby="llm-title"
      onCancel={e => { e.preventDefault(); onClose() }}
    >
      <div className="llm-heading">
        <h2 id="llm-title">LLM settings</h2>
        <button type="button" className="teach-btn" onClick={onClose} aria-label="Close LLM settings">
          Close
        </button>
      </div>
      <p>One selection for chat, quizzes and study. Clear it to use environment defaults.</p>
      <form onSubmit={e => { e.preventDefault(); act('save') }}>
        <fieldset disabled={busy || !spec}>
          <label>
            Provider
            <select value={form.provider} onChange={e => chooseProvider(e.target.value)}>
              {providers.map(p => <option key={p.id} value={p.id}>{p.label}</option>)}
            </select>
          </label>
          {form.provider !== 'azure_openai' && (
            <label>
              {form.provider === 'custom' ? 'LangChain provider:model' : 'Model (choose or type)'}
              <input
                list="llm-models"
                value={form.model}
                onChange={e => setField('model', e.target.value)}
                placeholder={form.provider === 'custom' ? 'openai:gpt-4o-mini' : 'Model name'}
                required
                maxLength={200}
              />
              <datalist id="llm-models">
                {spec?.models.map(model => <option key={model} value={model} />)}
              </datalist>
            </label>
          )}
          {form.provider === 'ollama' && (
            <label>
              Ollama base URL (from the server)
              <input type="url" value={form.base_url || ''} onChange={e => setField('base_url', e.target.value)} />
            </label>
          )}
          {form.provider === 'azure_openai' && (
            <>
              <label>
                Azure endpoint
                <input type="url" value={form.endpoint || ''} onChange={e => setField('endpoint', e.target.value)} placeholder="https://resource.openai.azure.com" required />
              </label>
              <label>
                API version
                <input value={form.api_version || ''} onChange={e => setField('api_version', e.target.value)} placeholder="2024-10-21" required />
              </label>
              <label>
                Deployment
                <input value={form.deployment || ''} onChange={e => setField('deployment', e.target.value)} required />
              </label>
            </>
          )}
          {form.provider !== 'ollama' && (
            <label>
              API key {keepsKey ? '(leave blank to keep saved key)' : form.provider === 'custom' ? '(optional)' : ''}
              <input
                type="password"
                autoComplete="new-password"
                value={apiKey}
                onChange={e => setApiKey(e.target.value)}
                placeholder={keepsKey ? saved.masked_key : ''}
                required={!keepsKey && form.provider !== 'custom'}
                maxLength={8192}
              />
            </label>
          )}
          <div className="llm-actions">
            <button type="submit" className="teach-btn">Save</button>
            <button type="button" className="teach-btn" onClick={() => act('test')}>Test connection</button>
          </div>
        </fieldset>
        <button type="button" className="teach-btn" disabled={busy} onClick={() => act('clear')}>
          Clear saved selection
        </button>
      </form>
      {busy && <p role="status">Working...</p>}
      {error && <p className="llm-error" role="alert">{error}</p>}
      {status && <p role="status">{status}</p>}
      <p className="llm-note">Keys are encrypted in Redis, never stored in browser storage. Test sends a short prompt to the selected provider and may incur a charge. Custom providers must already be installed on the server. Study progress and chat history are still shared.</p>
    </dialog>
  )
}
