import React, { useState } from "react";
import RequestForm from "./components/RequestForm";
import ConnectionDetailsForm from "./components/ConnectionDetailsForm";
import ResultView from "./components/ResultView";

const API_BASE = "http://localhost:5001/api";

// step: "describe" -> "details" -> "result"
function App() {
  const [step, setStep] = useState("describe");
  const [spec, setSpec] = useState(null);
  const [result, setResult] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [fieldErrors, setFieldErrors] = useState(null); // CHANGE 2

  const handleParse = async (text) => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`${API_BASE}/parse`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ request: text }),
      });
      const data = await response.json();
      if (!response.ok) {
        setError(typeof data.detail === "string" ? data.detail : "Something went wrong.");
      } else {
        setSpec(data);
        setStep("details");
      }
    } catch (err) {
      setError("Could not reach the backend. Is it running on port 5001?");
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async (formData) => {
    setLoading(true);
    setError(null);
    setFieldErrors(null);
    try {
      const response = await fetch(`${API_BASE}/onboard`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(formData),
      });
      const data = await response.json();

      if (!response.ok) {
        // CHANGE 2: backend now sends {message, field_errors} instead of
        // a single string, so show each error next to its own field.
        const detail = data.detail;
        if (detail && typeof detail === "object") {
          setError(detail.message || "Please fix the highlighted fields.");
          setFieldErrors(detail.field_errors || {});
        } else {
          setError(detail || "Something went wrong.");
        }
      } else {
        setResult(data);
        setStep("result");
      }
    } catch (err) {
      setError("Could not reach the backend. Is it running on port 5001?");
    } finally {
      setLoading(false);
    }
  };

  const handleStartOver = () => {
    setSpec(null);
    setResult(null);
    setError(null);
    setFieldErrors(null);
    setStep("describe");
  };

  return (
    <div className="app">
      <h1>Data Source Onboarding & Connector Generation Agent</h1>

      {step === "describe" && (
        <RequestForm onParse={handleParse} loading={loading} />
      )}

      {step === "details" && spec && (
        <ConnectionDetailsForm
          spec={spec}
          onGenerate={handleGenerate}
          onBack={handleStartOver}
          loading={loading}
          fieldErrors={fieldErrors}
        />
      )}

      {error && <p className="error">{error}</p>}

      {step === "result" && (
        <ResultView result={result} onStartOver={handleStartOver} />
      )}
    </div>
  );
}

export default App;