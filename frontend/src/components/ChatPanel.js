import React, { useEffect, useRef, useState } from "react";
import GenerationResult from "./GenerationResult";

const QUICK_ACTIONS = [
  { label: "Connect PostgreSQL", message: "Connect to our PostgreSQL sales database" },
  { label: "Connect Stripe REST API", message: "Connect to the Stripe REST API using an API key" },
  { label: "Disambiguate SQL", message: "Connect to my SQL database" },
  { label: "Generate with dummy data", message: "Just generate it with dummy/placeholder values", dummy: true },
];

function ChatPanel({ messages, onSend, loading }) {
  const [text, setText] = useState("");
  const feedRef = useRef(null);

  useEffect(() => {
    if (feedRef.current) {
      feedRef.current.scrollTop = feedRef.current.scrollHeight;
    }
  }, [messages, loading]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!text.trim() || loading) return;
    onSend(text.trim(), false);
    setText("");
  };

  const handleQuickAction = (action) => {
    if (loading) return;
    onSend(action.message, !!action.dummy);
  };

  return (
    <div className="chat-panel">
      <div className="chat-feed" ref={feedRef}>
        {messages.length === 0 && (
          <div className="chat-empty">
            <p>Describe a data source you want to onboard, or pick a quick action below.</p>
          </div>
        )}

        {messages.map((m, i) =>
          m.type === "generation" ? (
            <GenerationResult key={i} result={m.result} />
          ) : (
            <div key={i} className={`chat-bubble chat-bubble-${m.role}`}>
              {m.content}
            </div>
          )
        )}

        {loading && (
          <div className="chat-bubble chat-bubble-assistant chat-typing">
            <span className="dot" />
            <span className="dot" />
            <span className="dot" />
          </div>
        )}
      </div>

      <div className="quick-actions">
        {QUICK_ACTIONS.map((action) => (
          <button
            key={action.label}
            type="button"
            className="quick-action-button"
            onClick={() => handleQuickAction(action)}
            disabled={loading}
          >
            {action.label}
          </button>
        ))}
      </div>

      <form className="chat-input-row" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Describe the data source you want to onboard..."
          value={text}
          onChange={(e) => setText(e.target.value)}
          disabled={loading}
        />
        <button type="submit" disabled={loading || !text.trim()}>
          Send
        </button>
      </form>
    </div>
  );
}

export default ChatPanel;