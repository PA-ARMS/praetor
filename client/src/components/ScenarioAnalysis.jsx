import React, { useState } from 'react'
import axios from 'axios'
import './ScenarioAnalysis.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

function ScenarioAnalysis() {
  const [facts, setFacts] = useState('')
  const [caseType, setCaseType] = useState('')
  const [jurisdiction, setJurisdiction] = useState('Virginia')
  const [loading, setLoading] = useState(false)
  const [prediction, setPrediction] = useState(null)
  const [similarScenarios, setSimilarScenarios] = useState([])
  const [error, setError] = useState(null)

  const handlePredict = async (e) => {
    e.preventDefault()
    if (!facts.trim()) return

    setLoading(true)
    setError(null)
    setPrediction(null)
    setSimilarScenarios([])

    try {
      const response = await axios.post(`${API_BASE}/api/scenarios/predict`, {
        facts: facts,
        case_type: caseType || null,
        jurisdiction: jurisdiction || null
      })

      setPrediction(response.data)
      
      // Also fetch similar scenarios
      if (response.data.top_similar_scenarios) {
        setSimilarScenarios(response.data.top_similar_scenarios)
      }
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to get prediction')
      console.error('Prediction error:', err)
    } finally {
      setLoading(false)
    }
  }

  const handleFindSimilar = async () => {
    if (!facts.trim()) return

    setLoading(true)
    setError(null)
    setSimilarScenarios([])

    try {
      const response = await axios.post(`${API_BASE}/api/scenarios/find-similar`, null, {
        params: {
          facts: facts,
          case_type: caseType || undefined,
          jurisdiction: jurisdiction || undefined,
          n_results: 10
        }
      })

      setSimilarScenarios(response.data.results || [])
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to find similar scenarios')
      console.error('Find similar error:', err)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="scenario-analysis">
      <div className="scenario-header">
        <h2>Scenario Analysis & Outcome Prediction</h2>
        <p>Enter case facts to predict likely outcomes based on similar historical cases</p>
      </div>

      <form className="scenario-form" onSubmit={handlePredict}>
        <div className="form-row">
          <div className="form-group">
            <label>Case Facts *</label>
            <textarea
              value={facts}
              onChange={(e) => setFacts(e.target.value)}
              placeholder="Describe the case facts, parties, and key issues..."
              rows={6}
              required
            />
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label>Case Type (Optional)</label>
            <select value={caseType} onChange={(e) => setCaseType(e.target.value)}>
              <option value="">Any</option>
              <option value="Contract">Contract</option>
              <option value="Tort">Tort</option>
              <option value="Criminal">Criminal</option>
              <option value="Family Law">Family Law</option>
              <option value="Employment">Employment</option>
              <option value="Property">Property</option>
            </select>
          </div>

          <div className="form-group">
            <label>Jurisdiction</label>
            <select value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)}>
              <option value="Virginia">Virginia</option>
              <option value="Federal">Federal</option>
              <option value="">Any</option>
            </select>
          </div>
        </div>

        <div className="form-actions">
          <button type="submit" disabled={loading || !facts.trim()} className="predict-button">
            {loading ? 'Analyzing...' : 'Predict Outcome'}
          </button>
          <button 
            type="button" 
            onClick={handleFindSimilar} 
            disabled={loading || !facts.trim()} 
            className="find-similar-button"
          >
            Find Similar Cases
          </button>
        </div>
      </form>

      {error && (
        <div className="error-message">
          {error}
        </div>
      )}

      {prediction && (
        <div className="prediction-results">
          <h3>Prediction Results</h3>
          
          <div className="prediction-main">
            <div className="prediction-outcome">
              <span className="label">Predicted Outcome:</span>
              <span className="value">{prediction.prediction}</span>
            </div>
            <div className="prediction-confidence">
              <span className="label">Confidence:</span>
              <span className="value">{prediction.confidence}%</span>
            </div>
            <div className="prediction-count">
              <span className="label">Based on:</span>
              <span className="value">{prediction.similar_scenarios} similar scenarios</span>
            </div>
          </div>

          {prediction.outcome_probabilities && Object.keys(prediction.outcome_probabilities).length > 0 && (
            <div className="probability-chart">
              <h4>Outcome Probabilities</h4>
              <div className="probabilities">
                {Object.entries(prediction.outcome_probabilities)
                  .sort((a, b) => b[1] - a[1])
                  .map(([outcome, prob]) => (
                    <div key={outcome} className="probability-item">
                      <div className="prob-label">{outcome}</div>
                      <div className="prob-bar-container">
                        <div 
                          className="prob-bar" 
                          style={{ width: `${prob}%` }}
                        />
                      </div>
                      <div className="prob-value">{prob}%</div>
                    </div>
                  ))}
              </div>
            </div>
          )}
        </div>
      )}

      {similarScenarios.length > 0 && (
        <div className="similar-scenarios">
          <h3>Similar Scenarios ({similarScenarios.length})</h3>
          <div className="scenarios-list">
            {similarScenarios.map((scenario, idx) => (
              <div key={idx} className="scenario-card">
                <div className="scenario-header-card">
                  <div className="scenario-outcome">{scenario.outcome}</div>
                  <div className="scenario-similarity">
                    {scenario.similarity_score 
                      ? `${Math.round(scenario.similarity_score * 100)}% similar`
                      : 'Similar'}
                  </div>
                </div>
                <div className="scenario-meta">
                  <span>{scenario.case_type}</span>
                  {scenario.jurisdiction && <span> • {scenario.jurisdiction}</span>}
                  {scenario.metadata?.court_level && <span> • {scenario.metadata.court_level}</span>}
                </div>
                <div className="scenario-text">
                  {scenario.text?.substring(0, 300)}...
                </div>
                {scenario.key_factors && scenario.key_factors.length > 0 && (
                  <div className="scenario-factors">
                    <strong>Key Factors:</strong> {scenario.key_factors.join(', ')}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {!prediction && !similarScenarios.length && !loading && (
        <div className="empty-state">
          <p>Enter case facts above to get outcome predictions and find similar cases.</p>
        </div>
      )}
    </div>
  )
}

export default ScenarioAnalysis

