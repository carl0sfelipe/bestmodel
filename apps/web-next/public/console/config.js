// Deployment configuration for the console.
// Empty string = same origin (needs a /v1/* proxy; web-next in production
// has none, so the static console must call the API cross-origin).
// For local development against a local API, set:
//   window.BESTMODEL_API = "http://localhost:8000";
window.BESTMODEL_API = window.BESTMODEL_API || "https://api.bestmodel.run";
