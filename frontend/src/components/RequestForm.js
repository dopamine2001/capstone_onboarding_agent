import React, { useState } from "react";

function RequestForm({ onParse, loading }) {
  const [text, setText] = useState("");

  const handleSubmit = (e) => {
    e.preventDefault();
    if (!text.trim()) return;
    onParse(text.trim());
  };

  return (
    <form className="request-form" onSubmit={handleSubmit}>
      <label htmlFor="request">Describe the data source you want to onboard</label>
      <textarea
        id="request"
        rows={4}
        placeholder='e.g. "Connect to our PostgreSQL sales database using username and password authentication"'
        value={text}
        onChange={(e) => setText(e.target.value)}
      />
      <button type="submit" disabled={loading}>
        {loading ? "Analyzing..." : "Analyze Request"}
      </button>
    </form>
  );
}

export default RequestForm;
