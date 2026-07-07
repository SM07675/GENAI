// Tiny audio utilities shared across components.

// Convert a Uint8Array of audio bytes to a base64 string (chunked to avoid
// call-stack limits on large blobs).
export function bytesToBase64(bytes) {
  let binary = "";
  const chunk = 0x8000;
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode.apply(null, bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}
