import React, { useState } from "react";

function ConnectionDetailsForm({ spec, onGenerate, onBack, loading }) {
  const isRestApi = spec.source_type === "rest_api";

  const [form, setForm] = useState({
    host: spec.host || "",
    port: spec.port || "",
    database: spec.database || spec.source_name || "",
    user: spec.user === "your_username" ? "" : spec.user || "",
    password: "",
    api_key: "",
  });

  const handleChange = (field) => (e) =>
    setForm({ ...form, [field]: e.target.value });

  const handleSubmit = (e) => {
    e.preventDefault();
    onGenerate({
      source_name: spec.source_name,
      source_type: spec.source_type,
      auth_method: spec.auth_method,
      raw_request: spec.raw_request,
      ...form,
      port: form.port ? Number(form.port) : null,
    });
  };

  return (
    <div className="details-form">
      <h2>Confirm connection details</h2>
      <p className="hint">
        The agent detected a <strong>{spec.source_type}</strong> source using{" "}
        <strong>{spec.auth_method}</strong> authentication. Enter the real
        details below — the connector, validation, and docs will be generated
        after you submit this.
      </p>

      <form onSubmit={handleSubmit} className="details-form-fields">
        <label>
          {isRestApi ? "Base URL" : "Host"}
          <input value={form.host} onChange={handleChange("host")} required />
        </label>

        {!isRestApi && (
          <>
            <label>
              Port
              <input value={form.port} onChange={handleChange("port")} />
            </label>
            <label>
              Database
              <input value={form.database} onChange={handleChange("database")} />
            </label>
            <label>
              Username
              <input value={form.user} onChange={handleChange("user")} />
            </label>
            <label>
              Password
              <input
                type="password"
                value={form.password}
                onChange={handleChange("password")}
              />
            </label>
          </>
        )}

        {isRestApi && (
          <label>
            API Key
            <input
              type="password"
              value={form.api_key}
              onChange={handleChange("api_key")}
            />
          </label>
        )}

        <div className="details-form-buttons">
          <button type="button" className="secondary" onClick={onBack}>
            Back
          </button>
          <button type="submit" disabled={loading}>
            {loading ? "Generating..." : "Generate Connector"}
          </button>
        </div>
      </form>
    </div>
  );
}

export default ConnectionDetailsForm;
