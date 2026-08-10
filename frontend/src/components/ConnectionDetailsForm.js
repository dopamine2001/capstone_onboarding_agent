import React, { useEffect, useState } from "react";

const API_BASE = "http://localhost:5001/api";

function ConnectionDetailsForm({ spec, onGenerate, onBack, loading, fieldErrors }) {
  const [fields, setFields] = useState([]);
  const [form, setForm] = useState({});
  const [fetchingSchema, setFetchingSchema] = useState(true);

  // CHANGE 1: fetch which fields this source type actually needs, instead
  // of a hardcoded one-size-fits-all form.
  useEffect(() => {
    let cancelled = false;
    setFetchingSchema(true);

    fetch(`${API_BASE}/fields/${spec.source_type}`)
      .then((res) => res.json())
      .then((data) => {
        if (cancelled) return;
        const fieldList = data.fields || [];
        setFields(fieldList);

        const initial = {};
        fieldList.forEach((f) => {
          if (f.name === "host") initial.host = spec.host || "";
          else if (f.name === "database")
            initial.database = spec.database || spec.source_name || "";
          else if (f.name === "user")
            initial.user = spec.user === "your_username" ? "" : spec.user || "";
          else initial[f.name] = f.default !== undefined ? f.default : "";
        });
        setForm(initial);
      })
      .finally(() => setFetchingSchema(false));

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [spec.source_type]);

  const handleChange = (name) => (e) =>
    setForm({ ...form, [name]: e.target.value });

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

  if (fetchingSchema) {
    return <p>Loading form for {spec.source_type}...</p>;
  }

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
        {fields.map((field) => (
          <label key={field.name}>
            {field.label}

            {field.type === "select" ? (
              <select
                value={form[field.name] ?? field.default ?? ""}
                onChange={handleChange(field.name)}
              >
                {field.options.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            ) : (
              <input
                type={
                  field.type === "password"
                    ? "password"
                    : field.type === "number"
                    ? "number"
                    : "text"
                }
                value={form[field.name] ?? ""}
                onChange={handleChange(field.name)}
              />
            )}

            {/* CHANGE 2: show the specific error for THIS field, if any */}
            {fieldErrors && fieldErrors[field.name] && (
              <span className="field-error">{fieldErrors[field.name]}</span>
            )}
          </label>
        ))}

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