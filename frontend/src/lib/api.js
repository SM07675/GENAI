// Small REST helpers for the (optional) non-WebSocket smoke-test endpoint.
// The UI primarily uses the WebSocket; this is a convenience for diagnostics.

// Backend base URL. Local dev -> 8765; mobile via ngrok -> same origin.
export function backendBase() {
  if (typeof window === "undefined") return "http://127.0.0.1:8765";
  const { hostname } = window.location;
  if (hostname === "localhost" || hostname === "127.0.0.1") {
    return "http://127.0.0.1:8765";
  }
  return `${window.location.protocol}//${window.location.host}`;
}

export async function fetchInfo() {
  const r = await fetch(`${backendBase()}/info`);
  if (!r.ok) throw new Error(`info failed: ${r.status}`);
  return r.json();
}

export async function fetchHealth() {
  const r = await fetch(`${backendBase()}/health`);
  if (!r.ok) throw new Error(`health failed: ${r.status}`);
  return r.json();
}
