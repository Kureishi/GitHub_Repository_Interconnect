import React, { useState } from 'react';
import useModuleStore from '../store/useModuleStore';
import api from '../api/client';

export default function AISettingsPanel() {
  const {
    lmStudioUrl,
    lmStudioModel,
    setLMStudioUrl,
    setLMStudioModel,
    showToast,
  } = useModuleStore();

  const [isOpen, setIsOpen] = useState(false);
  const [checking, setChecking] = useState(false);
  const [status, setStatus] = useState(null); // null | 'ok' | 'error'
  const [availableModels, setAvailableModels] = useState([]);
  const [errorMessage, setErrorMessage] = useState('');

  const checkConnection = async () => {
    setChecking(true);
    setStatus(null);
    setErrorMessage('');
    try {
      const res = await api.get('/api/llm/health', {
        params: { lm_url: lmStudioUrl },
      });
      setStatus('ok');
      const models = res.data.models || [];
      setAvailableModels(models);
      if (models.length > 0 && !lmStudioModel) {
        setLMStudioModel(models[0]);
      }
      showToast('Connected to LM Studio successfully!', 'success');
    } catch (e) {
      setStatus('error');
      const msg = e.response?.data?.detail || e.message || 'Connection failed';
      setErrorMessage(msg);
      showToast('Could not connect to LM Studio', 'error');
    } finally {
      setChecking(false);
    }
  };

  return (
    <div className="ai-settings-card">
      <button
        className="ai-settings-toggle"
        onClick={() => setIsOpen(!isOpen)}
        title="Toggle LM Studio AI Settings"
      >
        <div className="flex items-center gap-2">
          <span className="ai-sparkle-icon">✨</span>
          <span className="text-sm font-semibold text-slate-200">LM Studio (Local LLM)</span>
        </div>
        <span className="text-xs text-slate-400">
          {isOpen ? '▲' : '▼'}
        </span>
      </button>

      {isOpen && (
        <div className="ai-settings-body">
          <div className="mb-3">
            <label className="text-xs text-slate-400 block mb-1">
              LM Studio Server URL
            </label>
            <input
              type="text"
              className="w-full bg-slate-800 border border-slate-700 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
              value={lmStudioUrl}
              onChange={(e) => setLMStudioUrl(e.target.value)}
              placeholder="http://localhost:1234"
            />
          </div>

          <div className="flex items-center gap-2 mb-3">
            <button
              onClick={checkConnection}
              disabled={checking}
              className="flex-1 bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700 hover:border-slate-600 rounded px-2.5 py-1.5 text-xs font-medium transition-colors flex items-center justify-center gap-1.5"
            >
              {checking ? (
                <>
                  <span className="animate-spin inline-block">⏳</span>
                  <span>Testing...</span>
                </>
              ) : (
                <>
                  <span>🔌</span>
                  <span>Test Connection</span>
                </>
              )}
            </button>

            {status === 'ok' && (
              <span className="text-xs bg-emerald-500/10 border border-emerald-500/30 text-emerald-400 px-2 py-1 rounded">
                ✅ Connected
              </span>
            )}
            {status === 'error' && (
              <span className="text-xs bg-rose-500/10 border border-rose-500/30 text-rose-400 px-2 py-1 rounded">
                ❌ Offline
              </span>
            )}
          </div>

          {status === 'error' && errorMessage && (
            <p className="text-xs text-rose-400 mb-2 leading-relaxed bg-rose-950/40 p-2 rounded border border-rose-900/40">
              {errorMessage}
            </p>
          )}

          {availableModels.length > 0 && (
            <div className="mb-2">
              <label className="text-xs text-slate-400 block mb-1">
                Active Model
              </label>
              <select
                className="w-full bg-slate-800 border border-slate-700 rounded px-2 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-indigo-500 font-mono"
                value={lmStudioModel}
                onChange={(e) => setLMStudioModel(e.target.value)}
              >
                {availableModels.map((m) => (
                  <option key={m} value={m}>
                    {m}
                  </option>
                ))}
              </select>
            </div>
          )}

          <p className="text-[11px] text-slate-500 mt-2 leading-relaxed">
            Powers AI endpoint discovery, natural language descriptions, and flow architecture reports.
          </p>
        </div>
      )}
    </div>
  );
}
