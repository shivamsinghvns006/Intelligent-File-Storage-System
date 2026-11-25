import { useCallback, useEffect, useState } from "react";

import { checkApiHealth, type ApiConnectionStatus } from "./health-client.mjs";

type ApiStatus = "checking" | ApiConnectionStatus;

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

function App() {
  const [apiStatus, setApiStatus] = useState<ApiStatus>("checking");

  const checkConnection = useCallback(async () => {
    setApiStatus("checking");
    setApiStatus(await checkApiHealth(API_BASE_URL));
  }, []);

  useEffect(() => {
    void checkConnection();
  }, [checkConnection]);

  const statusLabel = {
    checking: "Checking API connection…",
    connected: "API connected",
    unavailable: "API unavailable",
  }[apiStatus];

  return (
    <main id="main-content" className="foundation-page">
      <header className="wordmark" aria-label="IFSS">
        <span className="wordmark-mark" aria-hidden="true">
          I
        </span>
        <span>IFSS</span>
      </header>

      <section className="intro" aria-labelledby="page-title">
        <p className="eyebrow">INTELLIGENT FILE STORAGE SYSTEM</p>
        <h1 id="page-title">A thoughtful workspace for the files that matter.</h1>
        <p className="intro-copy">
          The application foundation is ready. File management, distributed storage,
          and AI workflows will arrive in their planned milestones.
        </p>
        <div className="foundation-status" role="status" aria-live="polite">
          <span
            className={`status-dot status-dot--${apiStatus}`}
            aria-hidden="true"
          />
          <span>{statusLabel}</span>
          {apiStatus === "unavailable" && (
            <button className="retry-button" type="button" onClick={checkConnection}>
              Retry
            </button>
          )}
        </div>
      </section>

      <footer className="page-footer">
        <span>Calm Precision</span>
        <span>Development foundation · No product data connected</span>
      </footer>
    </main>
  );
}

export default App;
