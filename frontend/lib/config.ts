// Base URL of the Flask API as seen from the browser.
export const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001").replace(/\/$/, "");

// Base URL of the Flask API as seen from the Next.js server (may differ inside Docker).
export const SERVER_API_BASE_URL = (process.env.BACKEND_URL || API_BASE_URL).replace(/\/$/, "");
