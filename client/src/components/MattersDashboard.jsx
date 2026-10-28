import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './MattersDashboard.css'
import { API_BASE } from '../apiConfig.js'

function getAuthHeaders() {
  const token = localStorage.getItem('token')
  const h = { 'Content-Type': 'application/json' }
  if (token) h['Authorization'] = `Bearer ${token}`
  return h
}

export default function MattersDashboard() {
  const [matters, setMatters] = useState([])
  const [upcoming, setUpcoming] = useState([])
  const [selectedMatter, setSelectedMatter] = useState(null)
  const [timeEntries, setTimeEntries] = useState([])
  const [docketEntries, setDocketEntries] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [view, setView] = useState('list') // list | create | detail
  const [conflictResult, setConflictResult] = useState(null)

  // Create form
  const [matterNumber, setMatterNumber] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [clientName, setClientName] = useState('')
  const [jurisdiction, setJurisdiction] = useState('Virginia')
  const [partyNames, setPartyNames] = useState('')
  const [notes, setNotes] = useState('')
  const [runConflictCheck, setRunConflictCheck] = useState(true)

  // Time entry form
  const [teDate, setTeDate] = useState(new Date().toISOString().slice(0, 10))
  const [teMinutes, setTeMinutes] = useState(60)
  const [teActivity, setTeActivity] = useState('research')
  const [teDescription, setTeDescription] = useState('')

  // Docket form
  const [dType, setDType] = useState('filing')
  const [dDueDate, setDDueDate] = useState('')
  const [dDescription, setDDescription] = useState('')

  const loadMatters = async () => {
    try {
      const r = await axios.get(`${API_BASE}/api/matters`, { headers: getAuthHeaders() })
      setMatters(r.data || [])
    } catch (e) {
      setError(e?.response?.data?.detail || e.message)
    }
  }

  const loadUpcoming = async () => {
    try {
      const r = await axios.get(`${API_BASE}/api/matters/calendar/upcoming?days=30`, { headers: getAuthHeaders() })
      setUpcoming(r.data || [])
    } catch (_) {}
  }

  useEffect(() => {
    (async () => {
      setLoading(true)
      setError(null)
      await loadMatters()
      await loadUpcoming()
      setLoading(false)
    })()
  }, [])

  const loadMatterDetail = async (matterId) => {
    try {
      const [m, te, d] = await Promise.all([
        axios.get(`${API_BASE}/api/matters/${matterId}`, { headers: getAuthHeaders() }),
        axios.get(`${API_BASE}/api/matters/${matterId}/time-entries`, { headers: getAuthHeaders() }),
        axios.get(`${API_BASE}/api/matters/${matterId}/docket`, { headers: getAuthHeaders() }),
      ])
      setSelectedMatter(m.data)
      setTimeEntries(te.data || [])
      setDocketEntries(d.data || [])
    } catch (e) {
      setError(e?.response?.data?.detail || e.message)
    }
  }

  const handleCreateMatter = async () => {
    setError(null)
    setConflictResult(null)
    if (runConflictCheck && (clientName.trim() || partyNames.trim())) {
      try {
        const cr = await axios.post(
          `${API_BASE}/api/matters/conflict-check`,
          { client_name: clientName.trim() || null, party_names: partyNames.trim() || null },
          { headers: getAuthHeaders() }
        )
        setConflictResult(cr.data)
        if (cr.data.has_conflict) return
      } catch (e) {
        setError(e?.response?.data?.detail || e.message)
        return
      }
    }
    try {
      await axios.post(
        `${API_BASE}/api/matters`,
        {
          matter_number: matterNumber.trim(),
          display_name: displayName.trim(),
          client_name: clientName.trim() || null,
          jurisdiction: jurisdiction || 'Virginia',
          party_names: partyNames.trim() || null,
          notes: notes.trim() || null,
        },
        { headers: getAuthHeaders() }
      )
      setView('list')
      setMatterNumber('')
      setDisplayName('')
      setClientName('')
      setPartyNames('')
      setNotes('')
      await loadMatters()
    } catch (e) {
      setError(e?.response?.data?.detail || e.message)
    }
  }

  const handleAddTimeEntry = async () => {
    if (!selectedMatter) return
    try {
      await axios.post(
        `${API_BASE}/api/matters/${selectedMatter.id}/time-entries`,
        {
          matter_id: selectedMatter.id,
          entry_date: teDate,
          duration_minutes: teMinutes,
          activity_type: teActivity,
          description: teDescription.trim() || null,
          billable: true,
        },
        { headers: getAuthHeaders() }
      )
      setTeDescription('')
      loadMatterDetail(selectedMatter.id)
    } catch (e) {
      setError(e?.response?.data?.detail || e.message)
    }
  }

  const handleAddDocket = async () => {
    if (!selectedMatter || !dDueDate) return
    try {
      await axios.post(
        `${API_BASE}/api/matters/${selectedMatter.id}/docket`,
        {
          matter_id: selectedMatter.id,
          deadline_type: dType,
          due_date: new Date(dDueDate).toISOString(),
          description: dDescription.trim() || null,
          reminder_days: 7,
        },
        { headers: getAuthHeaders() }
      )
      setDDueDate('')
      setDDescription('')
      loadMatterDetail(selectedMatter.id)
      loadUpcoming()
    } catch (e) {
      setError(e?.response?.data?.detail || e.message)
    }
  }

  const toggleDocketComplete = async (docketId, completed) => {
    try {
      await axios.patch(
        `${API_BASE}/api/matters/docket/${docketId}`,
        { completed },
        { headers: getAuthHeaders() }
      )
      if (selectedMatter) loadMatterDetail(selectedMatter.id)
      loadUpcoming()
    } catch (e) {
      setError(e?.response?.data?.detail || e.message)
    }
  }

  if (loading) {
    return (
      <div className="matters-dashboard">
        <p className="matters-loading">Loading matters...</p>
      </div>
    )
  }

  if (view === 'create') {
    return (
      <div className="matters-dashboard">
        <h2>New Matter</h2>
        {error && <div className="matters-err">{error}</div>}
        {conflictResult?.has_conflict && (
          <div className="matters-conflict">
            <strong>Conflict check found potential conflicts:</strong>
            <ul>
              {conflictResult.conflicts.map((c, i) => (
                <li key={i}>{c.matter_number}: {c.reason}</li>
              ))}
            </ul>
            <p>Resolve before opening this matter, or uncheck &quot;Run conflict check&quot; to proceed anyway.</p>
          </div>
        )}
        <div className="matters-form">
          <label>Matter number *</label>
          <input value={matterNumber} onChange={(e) => setMatterNumber(e.target.value)} placeholder="e.g. 2024-001" />
          <label>Display name *</label>
          <input value={displayName} onChange={(e) => setDisplayName(e.target.value)} placeholder="Short description" />
          <label>Client name</label>
          <input value={clientName} onChange={(e) => setClientName(e.target.value)} placeholder="Client or firm name" />
          <label>Jurisdiction</label>
          <select value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)}>
            <option value="Virginia">Virginia</option>
            <option value="Federal">Federal</option>
            <option value="Multi">Multi</option>
          </select>
          <label>Party names (comma-separated, for conflict check)</label>
          <input value={partyNames} onChange={(e) => setPartyNames(e.target.value)} placeholder="Smith, Jones, ABC Corp" />
          <label>Notes</label>
          <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={2} />
          <label>
            <input type="checkbox" checked={runConflictCheck} onChange={(e) => setRunConflictCheck(e.target.checked)} />
            Run conflict check before creating
          </label>
          <div className="matters-actions">
            <button type="button" className="matters-btn primary" onClick={handleCreateMatter}>
              Create matter
            </button>
            <button type="button" className="matters-btn" onClick={() => { setView('list'); setError(null); setConflictResult(null); }}>
              Cancel
            </button>
          </div>
        </div>
      </div>
    )
  }

  if (view === 'detail' && selectedMatter) {
    const totalMinutes = timeEntries.reduce((s, e) => s + (e.duration_minutes || 0), 0)
    return (
      <div className="matters-dashboard">
        <button type="button" className="matters-back" onClick={() => { setView('list'); setSelectedMatter(null); setError(null); }}>
          ← Back to matters
        </button>
        <h2>{selectedMatter.matter_number} — {selectedMatter.display_name}</h2>
        <p className="matter-meta">
          {selectedMatter.client_name && <span>Client: {selectedMatter.client_name}</span>}
          {selectedMatter.jurisdiction && <span>Jurisdiction: {selectedMatter.jurisdiction}</span>}
          <span>Status: {selectedMatter.status}</span>
        </p>
        {error && <div className="matters-err">{error}</div>}

        <section className="matters-section">
          <h3>Time entries</h3>
          <div className="time-summary">Total: {Math.floor(totalMinutes / 60)}h {totalMinutes % 60}m</div>
          <div className="matters-subform">
            <input type="date" value={teDate} onChange={(e) => setTeDate(e.target.value)} />
            <input type="number" min={1} value={teMinutes} onChange={(e) => setTeMinutes(Number(e.target.value))} placeholder="Minutes" />
            <select value={teActivity} onChange={(e) => setTeActivity(e.target.value)}>
              <option value="research">Research</option>
              <option value="drafting">Drafting</option>
              <option value="review">Review</option>
              <option value="hearing">Hearing</option>
              <option value="conference">Conference</option>
              <option value="other">Other</option>
            </select>
            <input type="text" value={teDescription} onChange={(e) => setTeDescription(e.target.value)} placeholder="Description" />
            <button type="button" className="matters-btn primary" onClick={handleAddTimeEntry}>Add time</button>
          </div>
          <ul className="time-list">
            {timeEntries.map((e) => (
              <li key={e.id}>
                {e.entry_date?.slice(0, 10)} — {e.duration_minutes}m — {e.activity_type}
                {e.description && ` — ${e.description}`}
              </li>
            ))}
          </ul>
        </section>

        <section className="matters-section">
          <h3>Docket / deadlines</h3>
          <div className="matters-subform">
            <select value={dType} onChange={(e) => setDType(e.target.value)}>
              <option value="filing">Filing</option>
              <option value="hearing">Hearing</option>
              <option value="statute_of_limitations">Statute of limitations</option>
              <option value="other">Other</option>
            </select>
            <input type="datetime-local" value={dDueDate} onChange={(e) => setDDueDate(e.target.value)} />
            <input type="text" value={dDescription} onChange={(e) => setDDescription(e.target.value)} placeholder="Description" />
            <button type="button" className="matters-btn primary" onClick={handleAddDocket} disabled={!dDueDate}>Add deadline</button>
          </div>
          <ul className="docket-list">
            {docketEntries.map((e) => (
              <li key={e.id} className={e.completed ? 'completed' : ''}>
                <input type="checkbox" checked={!!e.completed} onChange={() => toggleDocketComplete(e.id, !e.completed)} />
                {e.due_date?.slice(0, 16)} — {e.deadline_type}
                {e.description && ` — ${e.description}`}
              </li>
            ))}
          </ul>
        </section>
      </div>
    )
  }

  return (
    <div className="matters-dashboard">
      <div className="matters-header">
        <h2>Matters</h2>
        <button type="button" className="matters-btn primary" onClick={() => { setView('create'); setError(null); setConflictResult(null); }}>
          + New matter
        </button>
      </div>
      {error && <div className="matters-err">{error}</div>}

      {upcoming.length > 0 && (
        <section className="matters-upcoming">
          <h3>Upcoming deadlines (30 days)</h3>
          <ul>
            {upcoming.slice(0, 10).map((u) => (
              <li key={u.id}>
                {u.due_date?.slice(0, 10)} — {u.matter_number}: {u.deadline_type}
                {u.description && ` — ${u.description}`}
              </li>
            ))}
          </ul>
        </section>
      )}

      <section className="matters-list">
        {matters.length === 0 ? (
          <p className="matters-empty">No matters yet. Create one to get started.</p>
        ) : (
          <ul>
            {matters.map((m) => (
              <li key={m.id}>
                <span className="matter-num">{m.matter_number}</span>
                <span className="matter-name">{m.display_name}</span>
                {m.client_name && <span className="matter-client">{m.client_name}</span>}
                <span className={`matter-status ${m.status}`}>{m.status}</span>
                <button type="button" className="matters-btn small" onClick={() => { setView('detail'); loadMatterDetail(m.id); }}>
                  Open
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  )
}
