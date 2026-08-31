// Deployment configuration for the console.
// Empty string = same origin (Vercel rewrite proxies /v1/* to the API).
// For local development against a local API, set:
//   window.BESTMODEL_API = "http://localhost:8000";
window.BESTMODEL_API = window.BESTMODEL_API || "";
