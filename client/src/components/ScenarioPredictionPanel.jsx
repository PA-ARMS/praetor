import React from 'react'
import './ScenarioPredictionPanel.css'

function ScenarioPredictionPanel({ prediction }) {
  // Always log what we receive - use a clear prefix
  console.log('=== SCENARIO PREDICTION PANEL RENDER ===');
  console.log('[PANEL] Received prediction:', prediction);
  console.log('[PANEL] Prediction type:', typeof prediction);
  console.log('[PANEL] Is null?', prediction === null);
  console.log('[PANEL] Is undefined?', prediction === undefined);
  console.log('[PANEL] Is object?', typeof prediction === 'object' && prediction !== null);
  
  if (prediction) {
    console.log('[PANEL] Full prediction data:', JSON.stringify(prediction, null, 2));
    console.log('[PANEL] Has prediction field:', !!prediction.prediction, 'Value:', prediction.prediction);
    console.log('[PANEL] Has confidence:', !!prediction.confidence, 'Value:', prediction.confidence);
    console.log('[PANEL] Has similar_scenarios:', !!prediction.similar_scenarios, 'Value:', prediction.similar_scenarios);
    console.log('[PANEL] Has top_similar_scenarios:', !!prediction.top_similar_scenarios);
    console.log('[PANEL] top_similar_scenarios type:', typeof prediction.top_similar_scenarios);
    console.log('[PANEL] top_similar_scenarios is array?', Array.isArray(prediction.top_similar_scenarios));
    console.log('[PANEL] top_similar_scenarios length:', prediction.top_similar_scenarios?.length || 0);
    console.log('[PANEL] Has outcome_probabilities:', !!prediction.outcome_probabilities);
    console.log('[PANEL] All prediction keys:', Object.keys(prediction));
  } else {
    console.log('[PANEL] NO PREDICTION DATA - showing empty state');
  }

  // Always render the panel - show empty state if no prediction
  if (!prediction) {
    return (
      <div className="scenario-panel" style={{ border: '2px solid rgba(212, 175, 55, 0.5)' }}>
        <div className="scenario-panel-header">
          <h3>📊 Outcome Prediction</h3>
        </div>
        <div className="scenario-panel-empty">
          <p>No prediction analysis available.</p>
          <p className="scenario-panel-hint">
            Ask a question about a case scenario to see predictive analysis here.
          </p>
          <p className="scenario-panel-hint" style={{ fontSize: '0.75rem', marginTop: '0.5rem', color: 'rgba(212, 175, 55, 0.8)' }}>
            Example: "What is the likely outcome if a plaintiff sues for breach of contract in Virginia?"
          </p>
          <p className="scenario-panel-hint" style={{ fontSize: '0.7rem', marginTop: '1rem', color: 'rgba(255, 255, 255, 0.5)' }}>
            Panel is visible and ready. Check console for debugging info.
          </p>
        </div>
      </div>
    )
  }

  // Show data if we have any meaningful prediction information
  // Even if similar_scenarios is 0, we should show what we have
  const hasData = !!(prediction.prediction && 
                  prediction.prediction !== "Insufficient data" && 
                  (prediction.confidence !== undefined && prediction.confidence !== null))
  
  const hasSimilarScenarios = (prediction.similar_scenarios || 0) > 0
  const hasTopSimilar = !!(prediction.top_similar_scenarios && prediction.top_similar_scenarios.length > 0)
  
  console.log('hasData check:', hasData);
  console.log('hasSimilarScenarios:', hasSimilarScenarios);
  console.log('prediction.prediction:', prediction.prediction);
  console.log('prediction.confidence:', prediction.confidence);
  console.log('prediction.similar_scenarios:', prediction.similar_scenarios);

  return (
    <div className="scenario-panel">
      <div className="scenario-panel-header">
        <h3>📊 Outcome Prediction Analysis</h3>
      </div>
      
      {!hasData ? (
        <div className="scenario-panel-empty">
          <p>{prediction.prediction === "Insufficient data" ? "Insufficient Data" : "Prediction data received but appears incomplete."}</p>
          {prediction.similar_scenarios === 0 && (
            <p className="scenario-panel-hint">
              No similar cases found in the scenario database. The database may need more case data.
            </p>
          )}
          {prediction.similar_scenarios > 0 && (
            <p className="scenario-panel-hint">
              Found {prediction.similar_scenarios} similar case(s), but prediction data is incomplete.
            </p>
          )}
          <p className="scenario-panel-hint" style={{ fontSize: '0.7rem', marginTop: '1rem', color: 'rgba(255, 255, 255, 0.5)' }}>
            Check browser console and server logs for debugging info.
          </p>
        </div>
      ) : (
      <div className="scenario-panel-content">
        {/* Main Prediction Stats */}
        <div className="scenario-panel-section">
          <div className="scenario-stats-grid">
            {prediction.prediction && (
            <div className="scenario-stat-item">
              <span className="scenario-stat-label">Predicted Outcome:</span>
              <span className="scenario-stat-value">{prediction.prediction}</span>
            </div>
            )}
            {prediction.confidence !== undefined && prediction.confidence !== null && (
            <div className="scenario-stat-item">
              <div className="scenario-stat-label">Confidence:</div>
              <div className="scenario-stat-value">{prediction.confidence}%</div>
              <div className="scenario-confidence-explanation">
                {prediction.confidence >= 70 ? 'High confidence - strong pattern match' :
                 prediction.confidence >= 50 ? 'Moderate confidence - reasonable pattern match' :
                 prediction.confidence >= 30 ? 'Low-moderate confidence - some pattern match' :
                 'Low confidence - limited pattern match'}
              </div>
            </div>
            )}
            {prediction.similar_scenarios !== undefined && prediction.similar_scenarios !== null && (
            <div className="scenario-stat-item">
              <span className="scenario-stat-label">Based on:</span>
              <span className="scenario-stat-value">{prediction.similar_scenarios} similar cases</span>
            </div>
            )}
          </div>
        </div>

        {/* Outcome Probabilities */}
        {prediction.outcome_probabilities && Object.keys(prediction.outcome_probabilities).length > 0 && (
          <div className="scenario-panel-section">
            <div className="scenario-section-title">Outcome Probabilities</div>
            <div className="scenario-prob-explanation-box">
              <span className="scenario-prob-explanation-icon">ℹ️</span>
              <span className="scenario-prob-explanation-text">
                These percentages represent how often each outcome occurred in similar historical cases. 
                Higher percentages indicate more likely outcomes based on {prediction.similar_scenarios} similar cases analyzed.
              </span>
            </div>
            <div className="scenario-prob-list">
              {Object.entries(prediction.outcome_probabilities)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 5)
                .map(([outcome, prob]) => {
                  let barColor = '#d4af37'; // Gold (default)
                  let explanation = '';
                  if (prob >= 50) {
                    barColor = '#28a745'; // Green (high probability)
                    explanation = 'Very likely outcome';
                  } else if (prob >= 30) {
                    barColor = '#ffc107'; // Yellow/Orange (medium)
                    explanation = 'Moderately likely outcome';
                  } else {
                    barColor = '#dc3545'; // Red (low probability)
                    explanation = 'Less likely outcome';
                  }
                  
                  return (
                    <div key={outcome} className="scenario-prob-item">
                      <div className="scenario-prob-header">
                        <div className="scenario-prob-outcome-wrapper">
                          <span className="scenario-prob-outcome">{outcome}</span>
                          <span className="scenario-prob-explanation-badge" title={explanation}>
                            {prob >= 50 ? '🔵' : prob >= 30 ? '🟡' : '🔴'}
                          </span>
                        </div>
                        <span className="scenario-prob-percent">{prob.toFixed(1)}%</span>
                      </div>
                      <div className="scenario-prob-bar-container">
                        <div 
                          className="scenario-prob-bar"
                          style={{
                            width: `${prob}%`,
                            backgroundColor: barColor,
                            boxShadow: `0 0 10px ${barColor}40`
                          }}
                        >
                          <span className="scenario-prob-bar-fill"></span>
                        </div>
                      </div>
                      <div className="scenario-prob-item-explanation">
                        {prob.toFixed(1)}% of similar cases resulted in this outcome
                      </div>
                    </div>
                  );
                })}
            </div>
          </div>
        )}

        {/* Referenced Cases */}
        {(() => {
          const similarScenarios = prediction.top_similar_scenarios || [];
          console.log('[PANEL] Checking referenced cases:', {
            has_top_similar: !!prediction.top_similar_scenarios,
            is_array: Array.isArray(prediction.top_similar_scenarios),
            length: similarScenarios.length,
            first_item: similarScenarios[0]
          });
          if (similarScenarios.length > 0) {
            console.log('[PANEL] Displaying referenced cases:', similarScenarios.length, similarScenarios);
            return true;
          }
          console.log('[PANEL] No referenced cases to display');
          return false;
        })() && (
          <div className="scenario-panel-section">
            <div className="scenario-section-title">
              Referenced Cases ({prediction.top_similar_scenarios.length})
            </div>
            <div className="scenario-cases-list">
              {prediction.top_similar_scenarios.slice(0, 10).map((scenario, idx) => (
                <div key={idx} className="scenario-case-item">
                  {/* Case Name */}
                  {scenario.case_name && (
                    <div className="scenario-case-name">{scenario.case_name}</div>
                  )}
                  
                  <div className="scenario-case-header">
                    {scenario.outcome && (
                      <span className="scenario-case-outcome">{scenario.outcome}</span>
                    )}
                    {scenario.similarity_score && (
                      <span className="scenario-case-similarity">
                        {(scenario.similarity_score * 100).toFixed(1)}% match
                      </span>
                    )}
                  </div>
                  
                  {/* Case Type and Jurisdiction */}
                  {(scenario.case_type || scenario.jurisdiction || scenario.court_level) && (
                    <div className="scenario-case-meta">
                      {scenario.case_type && (
                        <span className="scenario-case-type">{scenario.case_type}</span>
                      )}
                      {scenario.jurisdiction && (
                        <span className="scenario-case-jurisdiction">{scenario.jurisdiction}</span>
                      )}
                      {scenario.court_level && (
                        <span className="scenario-case-court">{scenario.court_level}</span>
                      )}
                    </div>
                  )}
                  
                  {/* Citation */}
                  {(scenario.citation || scenario.metadata?.citation) && (
                    <div className="scenario-case-citation">
                      {scenario.citation || scenario.metadata?.citation}
                    </div>
                  )}
                  
                  {/* Text Excerpt */}
                  {scenario.text && (
                    <div className="scenario-case-excerpt">
                      {scenario.text.substring(0, 200)}
                      {scenario.text.length > 200 ? '...' : ''}
                    </div>
                  )}
                  
                  {/* Key Factors */}
                  {scenario.key_factors && scenario.key_factors.length > 0 && (
                    <div className="scenario-case-factors">
                      <strong>Key Factors:</strong> {
                        Array.isArray(scenario.key_factors) 
                          ? scenario.key_factors.join(', ')
                          : scenario.key_factors
                      }
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
      )}
    </div>
  )
}

export default ScenarioPredictionPanel

