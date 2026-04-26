import { useState } from 'react';
import ReactMarkdown from 'react-markdown';
import './Stage3.css';

export default function Stage3({ finalResponse, onFeedback, existingFeedback }) {
  const [submitted, setSubmitted] = useState(existingFeedback?.rating ?? null);

  if (!finalResponse) return null;

  const handleFeedback = async (rating) => {
    setSubmitted(rating);
    if (onFeedback) onFeedback(rating);
  };

  return (
    <div className="stage stage3">
      <h3 className="stage-title">Stage 3: Final Council Answer</h3>
      <div className="final-response">
        <div className="chairman-label">
          Chairman: {finalResponse.model.split('/')[1] || finalResponse.model}
        </div>
        <div className="final-text markdown-content">
          <ReactMarkdown>{finalResponse.response}</ReactMarkdown>
        </div>
        <div className="feedback-row">
          <span className="feedback-label">Was this helpful?</span>
          <button
            className={`feedback-btn thumbs-up ${submitted === 1 ? 'selected' : ''}`}
            onClick={() => handleFeedback(1)}
            disabled={submitted !== null}
            title="Thumbs up"
          >
            👍
          </button>
          <button
            className={`feedback-btn thumbs-down ${submitted === -1 ? 'selected' : ''}`}
            onClick={() => handleFeedback(-1)}
            disabled={submitted !== null}
            title="Thumbs down"
          >
            👎
          </button>
          {submitted !== null && (
            <span className="feedback-thanks">
              {submitted === 1 ? 'Thanks! Recorded.' : 'Noted. Thanks for the feedback.'}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
