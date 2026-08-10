import React from "react";

const API_BASE = "http://localhost:5001/api";

function ResultView({ result, onStartOver }) {
  if (!result) return null;

  const { id, spec, code, validation, documentation } = result;
  const connStatus = validation.connection_test.status;

  return (
    <div className="result-view">
      <h2>Extracted Spec</h2>
      <table>
        <tbody>
          <tr><td>Source Name</td><td>{spec.source_name}</td></tr>
          <tr><td>Source Type</td><td>{spec.source_type}</td></tr>
          <tr><td>Auth Method</td><td>{spec.auth_method}</td></tr>
          <tr><td>Host</td><td>{spec.host}</td></tr>
        </tbody>
      </table>

      <h2>Validation (real connection test)</h2>
      <p>
        Syntax valid: <strong>{validation.syntax_valid ? "Yes" : "No"}</strong>
        {validation.syntax_error && ` (${validation.syntax_error})`}
      </p>
      <p className={`live-result live-result-${connStatus}`}>
        <strong>{connStatus}</strong>: {validation.connection_test.message}
      </p>

      {/* CHANGE 4: downloadable files, in addition to the text shown here */}
      <div className="download-row">
        <a
          className="download-button"
          href={`${API_BASE}/connectors/${id}/download/code`}
          download
        >
          Download Code (.py)
        </a>
        <a
          className="download-button"
          href={`${API_BASE}/connectors/${id}/download/docs`}
          download
        >
          Download Documentation (.md)
        </a>
      </div>

      <h2>Generated Connector Code</h2>
      <pre className="code-block">{code}</pre>

      <h2>Documentation</h2>
      <pre className="code-block">{documentation}</pre>

      <button className="secondary" onClick={onStartOver}>
        Onboard Another Source
      </button>
    </div>
  );
}

export default ResultView;