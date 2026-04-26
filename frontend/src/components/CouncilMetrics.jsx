import './CouncilMetrics.css';

export default function CouncilMetrics({
  stage1Tokens,
  stage2Tokens,
  stage3Tokens,
  summary,
  consensus,
}) {
  if (!summary && !stage1Tokens && !stage2Tokens && !stage3Tokens) {
    return null;
  }

  return (
    <div className="council-metrics">
      {/* Cost Summary */}
      {summary?.total_cost !== undefined && (
        <div className="metrics-section cost-section">
          <h4>💰 Cost Breakdown</h4>
          <div className="cost-breakdown">
            <div className="cost-item">
              <span>Stage 1:</span>
              <span className="cost-value">${stage1Tokens?.total_cost?.toFixed(4) || '0.0000'}</span>
            </div>
            <div className="cost-item">
              <span>Stage 2:</span>
              <span className="cost-value">${stage2Tokens?.total_cost?.toFixed(4) || '0.0000'}</span>
            </div>
            <div className="cost-item">
              <span>Stage 3:</span>
              <span className="cost-value">${stage3Tokens?.total_cost?.toFixed(4) || '0.0000'}</span>
            </div>
            <div className="cost-item total">
              <span>Total:</span>
              <span className="cost-value cost-total">${summary?.total_cost?.toFixed(4) || '0.0000'}</span>
            </div>
          </div>
        </div>
      )}

      {/* Token Usage */}
      {summary?.total_tokens !== undefined && (
        <div className="metrics-section tokens-section">
          <h4>🔤 Token Usage</h4>
          <div className="tokens-info">
            <div className="token-stat">
              <span className="label">Total Tokens:</span>
              <span className="value">{summary.total_tokens?.toLocaleString() || 0}</span>
            </div>
            <div className="token-breakdown">
              <span className="stage-label">Stage 1: {stage1Tokens?.total_tokens || 0}</span>
              <span className="stage-label">Stage 2: {stage2Tokens?.total_tokens || 0}</span>
              <span className="stage-label">Stage 3: {stage3Tokens?.total_tokens || 0}</span>
            </div>
          </div>
        </div>
      )}

      {/* Consensus & Confidence */}
      {consensus && (
        <div className="metrics-section consensus-section">
          <h4>🎯 Council Consensus</h4>
          <div className="consensus-info">
            <div className="confidence-bar">
              <div className="confidence-label">
                <span>Confidence Level</span>
                <span className="confidence-pct">{(consensus.confidence * 100).toFixed(0)}%</span>
              </div>
              <div className="progress-bar">
                <div
                  className="progress-fill"
                  style={{
                    width: `${consensus.confidence * 100}%`,
                    backgroundColor:
                      consensus.confidence >= 0.8
                        ? '#4caf50'
                        : consensus.confidence >= 0.6
                        ? '#ff9800'
                        : '#f44336',
                  }}
                />
              </div>
            </div>

            <div className="consensus-stat">
              <span className="label">Consensus:</span>
              <span className="value">{consensus.consensus_percentage?.toFixed(0)}% Agreement</span>
            </div>

            {consensus.dissenting_views && consensus.dissenting_views.length > 0 && (
              <div className="dissenting-section">
                <div className="dissenting-label">Alternative Views:</div>
                <div className="dissenting-list">
                  {consensus.dissenting_views.map((dissent, idx) => (
                    <div key={idx} className="dissent-item">
                      <span className="dissent-model">{dissent.response_model}</span>
                      <span className="dissent-votes">
                        {dissent.vote_count} model{dissent.vote_count > 1 ? 's' : ''} ({dissent.percentage.toFixed(0)}%)
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {consensus.dissenting_views?.length === 0 && (
              <div className="full-agreement">
                <span className="checkmark">✓</span>
                <span className="agreement-text">Full Council Agreement</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
