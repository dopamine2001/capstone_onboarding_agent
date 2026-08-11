import React from "react";

const API_BASE = "http://localhost:5001/api";

function StatusBadge({ status }) {
  return <span className={`status-badge status-badge-${status}`}>{status}</span>;
}

function GenerationResult({ result }) {
  return (
    <div className="generation-bubble">
      <div className="badge-row">
        <StatusBadge status={result.validation.syntax_valid ? "syntax-ok" : "syntax-error"} />
        <StatusBadge status={result.validation.connection_test.status} />
      </div>
      <p className="connection-message">{result.validation.connection_test.message}</p>

      <div className="download-row">
        <a
          className="download-button"
          href={`${API_BASE}/connectors/${result.id}/download/code`}
          download
        >
          Download .py
        </a>
        <a
          className="download-button"
          href={`${API_BASE}/connectors/${result.id}/download/docs`}
          download
        >
          Download .pdf
        </a>
        <a
          className="download-button"
          href={`${API_BASE}/connectors/${result.id}/download/bundle`}
          download
        >
          Download .zip bundle
        </a>
      </div>

      <h4>Generated Connector Code</h4>
      <pre className="code-block">{result.code}</pre>

      <h4>Documentation</h4>
      <pre className="doc-viewer">{result.documentation}</pre>
    </div>
  );
}

export default GenerationResult;