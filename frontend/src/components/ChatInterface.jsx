import { useState, useEffect, useRef } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import CouncilMetrics from './CouncilMetrics';
import './ChatInterface.css';

const TEMPLATES = [
  { label: 'Compare tools', prompt: 'Compare [Tool A] vs [Tool B]: pros, cons, and when to use each.' },
  { label: 'Code review', prompt: 'Review this code and suggest improvements:\n\n```\n[paste code here]\n```' },
  { label: 'Debate both sides', prompt: 'Argue both sides of: [topic]' },
  { label: 'Research synthesis', prompt: 'Synthesize the current state of research on: [topic]' },
];

function exportToMarkdown(conversation) {
  const lines = [`# ${conversation.title || 'LLM Council Conversation'}`, ''];
  for (const msg of conversation.messages) {
    if (msg.role === 'user') {
      lines.push('## You', '', msg.content, '');
    } else {
      lines.push('## LLM Council', '');
      if (msg.stage3?.response) {
        lines.push('### Final Answer', '', msg.stage3.response, '');
      }
      if (msg.stage1?.length) {
        lines.push('### Individual Responses', '');
        for (const r of msg.stage1) {
          lines.push(`**${r.model.split('/')[1] || r.model}**`, '', r.response, '');
        }
      }
    }
  }
  return lines.join('\n');
}

export default function ChatInterface({
  conversation,
  onSendMessage,
  onFeedback,
  isLoading,
}) {
  const [input, setInput] = useState('');
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [conversation]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  const handleExport = () => {
    if (!conversation) return;
    const md = exportToMarkdown(conversation);
    const blob = new Blob([md], { type: 'text/markdown' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `${(conversation.title || 'conversation').replace(/[^a-z0-9]/gi, '_')}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>Welcome to LLM Council</h2>
          <p>Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      {/* Header */}
      <div className="chat-header">
        <span className="chat-title">{conversation.title || 'New Conversation'}</span>
        {conversation.messages.length > 0 && (
          <button className="export-btn" onClick={handleExport} title="Export to Markdown">
            ↓ Export
          </button>
        )}
      </div>

      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Ask the Council</h2>
            <p>Consult multiple AI models and get a synthesized answer.</p>
            <div className="templates">
              {TEMPLATES.map((t) => (
                <button
                  key={t.label}
                  className="template-btn"
                  onClick={() => setInput(t.prompt)}
                >
                  {t.label}
                </button>
              ))}
            </div>
          </div>
        ) : (
          conversation.messages.map((msg, index) => (
            <div key={index} className="message-group">
              {msg.role === 'user' ? (
                <div className="user-message">
                  <div className="message-label">You</div>
                  <div className="message-content">
                    <div className="markdown-content">
                      <ReactMarkdown>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              ) : (
                <div className="assistant-message">
                  <div className="message-label">LLM Council</div>

                  {msg.loading?.stage1 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 1: Collecting individual responses...</span>
                    </div>
                  )}
                  {msg.stage1 && <Stage1 responses={msg.stage1} />}

                  {msg.loading?.stage2 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 2: Peer rankings...</span>
                    </div>
                  )}
                  {msg.stage2 && (
                    <Stage2
                      rankings={msg.stage2}
                      labelToModel={msg.metadata?.label_to_model}
                      aggregateRankings={msg.metadata?.aggregate_rankings}
                      consensus={msg.metadata?.consensus}
                    />
                  )}

                  {msg.loading?.stage3 && (
                    <div className="stage-loading">
                      <div className="spinner"></div>
                      <span>Running Stage 3: Final synthesis...</span>
                    </div>
                  )}
                  {msg.stage3 && (
                    <Stage3
                      finalResponse={msg.stage3}
                      existingFeedback={msg.feedback}
                      onFeedback={(rating) => onFeedback && onFeedback(index, rating)}
                    />
                  )}

                  {msg.summary && (
                    <CouncilMetrics
                      stage1Tokens={msg.stage1_tokens}
                      stage2Tokens={msg.stage2_tokens}
                      stage3Tokens={msg.stage3_tokens}
                      summary={msg.summary}
                      consensus={msg.metadata?.consensus}
                    />
                  )}
                </div>
              )}
            </div>
          ))
        )}

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Consulting the council...</span>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <form className="input-form" onSubmit={handleSubmit}>
        <textarea
          className="message-input"
          placeholder="Ask your question... (Shift+Enter for new line, Enter to send)"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          rows={3}
        />
        <button
          type="submit"
          className="send-button"
          disabled={!input.trim() || isLoading}
        >
          Send
        </button>
      </form>
    </div>
  );
}
