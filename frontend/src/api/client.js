/**
 * Axios API client + WebSocket manager for analysis streaming.
 */
import axios from 'axios';

const api = axios.create({
  baseURL: '',          // Vite proxy handles /api/* → backend
  timeout: 30_000,
  headers: { 'Content-Type': 'application/json' },
});

export default api;

// ---------------------------------------------------------------------------
// WebSocket analysis stream
// ---------------------------------------------------------------------------

/**
 * Connect to the backend WebSocket and stream analysis progress.
 *
 * @param {string} repoUrl
 * @param {string|null} githubToken
 * @param {(progress: object) => void} onProgress  — called for each event
 * @returns {() => void}  — call to cancel / close the socket
 */
export function startAnalysis(repoUrl, githubToken, onProgress) {
  // Determine WS URL — in dev Vite proxies /ws to backend
  const proto = location.protocol === 'https:' ? 'wss' : 'ws';
  const wsUrl = `${proto}://${location.host}/ws/analyze`;

  const ws = new WebSocket(wsUrl);

  ws.addEventListener('open', () => {
    ws.send(JSON.stringify({
      repo_url: repoUrl,
      github_token: githubToken || null,
    }));
  });

  ws.addEventListener('message', (ev) => {
    try {
      const data = JSON.parse(ev.data);
      onProgress(data);
    } catch (e) {
      console.error('WS parse error', e);
    }
  });

  ws.addEventListener('error', (ev) => {
    onProgress({
      status: 'error',
      message: 'WebSocket connection failed. Is the backend running?',
      progress: 0,
      error: 'WebSocket error',
    });
  });

  ws.addEventListener('close', () => {
    // Nothing to do — final event already handled by onProgress
  });

  // Return a cancel function
  return () => {
    if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
      ws.close();
    }
  };
}
