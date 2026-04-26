import { useState, useEffect } from 'react';
import { api } from '../api';
import './Leaderboard.css';

export default function Leaderboard({ onClose }) {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getLeaderboard()
      .then(setData)
      .catch(() => setError('Failed to load leaderboard'))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="leaderboard-overlay" onClick={onClose}>
      <div className="leaderboard-modal" onClick={(e) => e.stopPropagation()}>
        <div className="leaderboard-header">
          <h2>Model Leaderboard</h2>
          <button className="leaderboard-close" onClick={onClose}>✕</button>
        </div>
        <p className="leaderboard-desc">
          Rankings based on peer evaluations and user feedback across all conversations.
        </p>

        {loading && <div className="leaderboard-loading">Loading...</div>}
        {error && <div className="leaderboard-error">{error}</div>}

        {!loading && !error && data.length === 0 && (
          <div className="leaderboard-empty">
            No data yet. Rankings will appear after conversations with feedback.
          </div>
        )}

        {!loading && data.length > 0 && (
          <table className="leaderboard-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Model</th>
                <th>Appearances</th>
                <th>Win Rate</th>
                <th>Avg Rank</th>
                <th>👍</th>
                <th>👎</th>
              </tr>
            </thead>
            <tbody>
              {data.map((row, i) => (
                <tr key={row.model} className={i === 0 ? 'top-row' : ''}>
                  <td className="rank-num">
                    {i === 0 ? '🥇' : i === 1 ? '🥈' : i === 2 ? '🥉' : i + 1}
                  </td>
                  <td className="model-name">{row.short_name}</td>
                  <td>{row.appearances}</td>
                  <td>
                    <div className="win-rate-bar">
                      <div
                        className="win-rate-fill"
                        style={{ width: `${row.win_rate}%` }}
                      />
                      <span>{row.win_rate}%</span>
                    </div>
                  </td>
                  <td>{row.avg_rank ?? '—'}</td>
                  <td className="thumbs-up-count">{row.thumbs_up}</td>
                  <td className="thumbs-down-count">{row.thumbs_down}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
