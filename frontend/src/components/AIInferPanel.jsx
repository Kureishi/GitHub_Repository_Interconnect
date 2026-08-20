import React, { useState, useEffect, useRef } from 'react';
import useModuleStore from '../store/useModuleStore';
import api from '../api/client';

export default function AIInferPanel() {
  const {
    activeAIInferModuleId,
    closeAIInfer,
    modules,
    updateModule,
    lmStudioUrl,
    lmStudioModel,
    githubToken,
    showToast,
  } = useModuleStore();

  const module = activeAIInferModuleId ? modules[activeAIInferModuleId] : null;

  const [isInferring, setIsInferring] = useState(false);
  const [isEnriching, setIsEnriching] = useState(false);
  const [progressMsg, setProgressMsg] = useState('');
  const [streamedText, setStreamedText] = useState('');
  const [inferredEndpoints, setInferredEndpoints] = useState([]);
  const wsRef = useRef(null);

  useEffect(() => {
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  if (!module) return null;

  const startInfer = () => {
    setIsInferring(true);
    setProgressMsg('Connecting to LM Studio...');
    setStreamedText('');
    setInferredEndpoints([]);

    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${window.location.host}/ws/llm/infer/${module.id}`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        lm_url: lmStudioUrl,
        model: lmStudioModel || null,
        github_token: githubToken || null,
      }));
    };

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.type === 'progress') {
          setProgressMsg(data.message);
        } else if (data.type === 'token') {
          setStreamedText((prev) => prev + data.text);
        } else if (data.type === 'done') {
          setInferredEndpoints(data.endpoints || []);
          setProgressMsg('Inference complete! New endpoints added to canvas.');
          showToast(`Inferred ${data.endpoints?.length || 0} endpoint(s) with AI!`, 'success');
        } else if (data.type === 'module_updated') {
          updateModule(data.module);
        } else if (data.type === 'error') {
          setProgressMsg(`Error: ${data.message}`);
          showToast(`AI Error: ${data.message}`, 'error');
          setIsInferring(false);
        }
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    ws.onerror = () => {
      setProgressMsg('WebSocket connection error. Is the backend running?');
      setIsInferring(false);
    };

    ws.onclose = () => {
      setIsInferring(false);
    };
  };

  const startEnrich = async () => {
    setIsEnriching(true);
    setProgressMsg('Calling LM Studio to enrich descriptions...');
    try {
      showToast('Enriching descriptions with LLM...', 'info');
      const res = await api.post(`/api/llm/enrich/${module.id}`, {
        lm_url: lmStudioUrl,
        model: lmStudioModel || null,
      });
      updateModule(res.data);
      setProgressMsg('Descriptions enriched successfully!');
      showToast('Endpoint descriptions enriched!', 'success');
    } catch (e) {
      const msg = e.response?.data?.detail || e.message;
      setProgressMsg(`Enrichment failed: ${msg}`);
      showToast(`Enrichment failed: ${msg}`, 'error');
    } finally {
      setIsEnriching(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={closeAIInfer}>
      <div
        className="modal-dialog modal-md"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <div className="modal-title-group">
            <span style={{ fontSize: 20 }}>✨</span>
            <div>
              <div className="modal-title">
                AI Interface Analysis — {module.owner}/{module.repo_name}
              </div>
              <div className="modal-subtitle">
                Local LLM ({lmStudioModel || 'default model'}) via LM Studio
              </div>
            </div>
          </div>
          <button
            onClick={closeAIInfer}
            className="modal-close-btn"
            title="Close"
          >
            ✕
          </button>
        </div>

        {/* Body */}
        <div className="modal-body">
          {/* Action Cards */}
          <div className="ai-actions-grid">
            <button
              onClick={startInfer}
              disabled={isInferring || isEnriching}
              className="ai-action-btn primary"
            >
              <div className="ai-action-btn-title">
                <span>✨ Infer Endpoints</span>
                {isInferring && <span className="spinner" />}
              </div>
              <p className="ai-action-btn-desc">
                Reads README & file trees to uncover hidden APIs, CLIs, schemas, or models missed by static analysis.
              </p>
            </button>

            <button
              onClick={startEnrich}
              disabled={isInferring || isEnriching}
              className="ai-action-btn"
            >
              <div className="ai-action-btn-title">
                <span>📝 Enrich Descriptions</span>
                {isEnriching && <span className="spinner" />}
              </div>
              <p className="ai-action-btn-desc">
                Rewrites terse static endpoint notes into clear, developer-friendly descriptions.
              </p>
            </button>
          </div>

          {/* Progress message */}
          {progressMsg && (
            <div
              style={{
                fontSize: 12,
                fontFamily: 'var(--font-mono)',
                background: 'var(--bg-deep)',
                border: '1px solid var(--border-subtle)',
                padding: '8px 12px',
                borderRadius: 'var(--r2)',
                color: 'var(--text-accent)',
                display: 'flex',
                alignItems: 'center',
                gap: 8,
              }}
            >
              {(isInferring || isEnriching) && <span className="spinner" />}
              <span>{progressMsg}</span>
            </div>
          )}

          {/* Streamed token output */}
          {streamedText && (
            <div>
              <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 6 }}>
                Live LLM Response Stream:
              </div>
              <div className="ai-stream-box">
                {streamedText}
              </div>
            </div>
          )}

          {/* Current endpoints summary */}
          <div>
            <div style={{ fontSize: 11, fontWeight: 600, color: 'var(--text-muted)', marginBottom: 8 }}>
              Current Endpoints ({module.endpoints?.length || 0})
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 180, overflowY: 'auto' }}>
              {module.endpoints?.map((ep) => (
                <div
                  key={ep.id}
                  style={{
                    background: 'var(--bg-elevated)',
                    border: '1px solid var(--border-subtle)',
                    borderRadius: 'var(--r2)',
                    padding: '6px 10px',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'space-between',
                    fontSize: 11,
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                    <span style={{ color: 'var(--text-muted)', fontFamily: 'var(--font-mono)', fontSize: 10 }}>
                      [{ep.type}]
                    </span>
                    <span style={{ color: 'var(--text-primary)', fontWeight: 600 }}>{ep.name}</span>
                    {ep.source === 'ai' && (
                      <span
                        style={{
                          background: 'rgba(155, 114, 255, 0.2)',
                          color: '#c084fc',
                          border: '1px solid rgba(155, 114, 255, 0.4)',
                          fontSize: 9,
                          padding: '1px 5px',
                          borderRadius: 4,
                          fontFamily: 'var(--font-mono)',
                        }}
                      >
                        ✨ AI
                      </span>
                    )}
                  </div>
                  <span
                    style={{
                      color: 'var(--text-secondary)',
                      fontSize: 10,
                      maxWidth: '45%',
                      overflow: 'hidden',
                      textOverflow: 'ellipsis',
                      whiteSpace: 'nowrap',
                    }}
                  >
                    {ep.description}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Endpoints update on the canvas in real time.
          </span>
          <button
            onClick={closeAIInfer}
            className="btn btn-secondary"
          >
            Done
          </button>
        </div>
      </div>
    </div>
  );
}
