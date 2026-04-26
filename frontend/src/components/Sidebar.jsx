import { useState, useEffect } from 'react';
import { api } from '../api';
import './Sidebar.css';

export default function Sidebar({
  conversations,
  currentConversationId,
  onSelectConversation,
  onNewConversation,
  onShowLeaderboard,
}) {
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState(null);
  const [searching, setSearching] = useState(false);

  useEffect(() => {
    const trimmed = searchQuery.trim();
    if (trimmed.length < 2) {
      setSearchResults(null);
      return;
    }
    const timer = setTimeout(async () => {
      setSearching(true);
      try {
        const results = await api.searchConversations(trimmed);
        setSearchResults(results);
      } catch {
        setSearchResults([]);
      } finally {
        setSearching(false);
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery]);

  const displayed = searchResults !== null ? searchResults : conversations;

  return (
    <div className="sidebar">
      <div className="sidebar-header">
        <h1>LLM Council</h1>
        <button className="new-conversation-btn" onClick={onNewConversation}>
          + New
        </button>
      </div>

      <div className="sidebar-search">
        <input
          type="text"
          className="search-input"
          placeholder="Search conversations..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        {searching && <span className="search-spinner">⟳</span>}
      </div>

      <div className="conversation-list">
        {displayed.length === 0 ? (
          <div className="no-conversations">
            {searchResults !== null ? 'No matches found' : 'No conversations yet'}
          </div>
        ) : (
          displayed.map((conv) => (
            <div
              key={conv.id}
              className={`conversation-item ${conv.id === currentConversationId ? 'active' : ''}`}
              onClick={() => onSelectConversation(conv.id)}
            >
              <div className="conversation-title">
                {conv.title || 'New Conversation'}
              </div>
              <div className="conversation-meta">
                {conv.message_count} message{conv.message_count !== 1 ? 's' : ''}
              </div>
            </div>
          ))
        )}
      </div>

      <div className="sidebar-footer">
        <button className="leaderboard-btn" onClick={onShowLeaderboard}>
          🏆 Leaderboard
        </button>
      </div>
    </div>
  );
}
