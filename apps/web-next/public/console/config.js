// Deployment configuration for the console.
// Empty string = same origin (Vercel rewrite proxies /v1/* to the API).
// On GitHub Pages (no proxy possible) the API base is absolute.
// For local development against a local API, set:
//   window.BESTMODEL_API = "http://localhost:8000";
window.BESTMODEL_API = window.BESTMODEL_API ||
  (location.hostname.endsWith(".github.io") ? "https://api.bestmodel.run" : "");
