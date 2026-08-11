import React, { useState } from "react";
import ChatPanel from "./components/ChatPanel";

const API_BASE = "http://localhost:5001/api";

function App() {
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleSend = async (text, dummyMode) => {
    setLoading(true);
    setError(null);
    setMessages((prev) => [...prev, { role: "user", type: "text", content: text }]);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          session_id: sessionId,
          message: text,
          dummy_mode: dummyMode,
        }),
      });
      const data = await response.json();

      if (!response.ok) {
        setError(typeof data.detail === "string" ? data.detail : "Something went wrong.");
        return;
      }

      setSessionId(data.session_id);
      setMessages((prev) => [...prev, { role: "assistant", type: "text", content: data.message }]);

      // Once the agent has gathered everything, the backend has ALREADY
      // run the connection test + generated the code + docs — show it
      // right in the chat feed, no separate panel needed.
      if (data.result) {
        setMessages((prev) => [
          ...prev,
          { role: "assistant", type: "generation", result: data.result },
        ]);
      }
    } catch (err) {
      setError("Could not reach the backend. Is it running on port 5001?");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Data Source Onboarding & Connector Generation Agent</h1>
      </header>

      {error && <p className="error">{error}</p>}

      <ChatPanel messages={messages} onSend={handleSend} loading={loading} />
    </div>
  );
}

export default App;