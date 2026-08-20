import { useState, useRef, useCallback } from 'react';
import { startAnalysis } from '../api/client';
import useModuleStore from '../store/useModuleStore';
import AISettingsPanel from './AISettingsPanel';

export default function AddRepoPanel() {
  const [repoUrl, setRepoUrl] = useState('');
  const [showToken, setShowToken] = useState(false);
  const cancelRef = useRef(null);

  const {
    analysisStatus,
    analysisProgress,
    analysisMessage,
    analysisError,
    githubToken,
    setGithubToken,
    setAnalysisState,
    addModule,
    showToast,
  } = useModuleStore();

  const isAnalyzing = analysisStatus === 'fetching' || analysisStatus === 'analyzing';

  const handleAnalyze = useCallback((e) => {
    e?.preventDefault();
    if (!repoUrl.trim() || isAnalyzing) return;

    setAnalysisState({
      analysisStatus: 'pending',
      analysisProgress: 0,
      analysisMessage: 'Connecting…',
      analysisError: null,
    });

    const cancel = startAnalysis(repoUrl.trim(), githubToken, (progress) => {
      setAnalysisState({
        analysisStatus: progress.status,
        analysisProgress: progress.progress || 0,
        analysisMessage: progress.message || '',
        analysisError: progress.error || null,
      });

      if (progress.status === 'done' && progress.module) {
        addModule(progress.module);
        showToast(`✅ Added: ${progress.module.full_name}`, 'success');
        setRepoUrl('');
      }

      if (progress.status === 'error') {
        showToast(`❌ ${progress.error || progress.message}`, 'error');
      }
    });

    cancelRef.current = cancel;
  }, [repoUrl, githubToken, isAnalyzing, setAnalysisState, addModule, showToast]);

  const handleCancel = () => {
    cancelRef.current?.();
    setAnalysisState({ analysisStatus: null, analysisProgress: 0, analysisMessage: '' });
  };

  const statusColor = {
    done: 'var(--accent-green)',
    error: 'var(--accent-red)',
    fetching: 'var(--accent-blue)',
    analyzing: 'var(--accent-purple)',
    pending: 'var(--text-muted)',
  }[analysisStatus] || 'var(--text-muted)';

  return (
    <div className="repo-form" id="add-repo-panel">
      <p className="section-label">Add Repository</p>

      <form onSubmit={handleAnalyze} className="flex flex-col gap-3">
        {/* URL input */}
        <div className="input-group">
          <label className="input-label" htmlFor="repo-url-input">
            GitHub URL or <span className="font-mono">owner/repo</span>
          </label>
          <input
            id="repo-url-input"
            className="input-field"
            type="text"
            placeholder="e.g. fastapi/fastapi"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            disabled={isAnalyzing}
            autoComplete="off"
            spellCheck={false}
          />
        </div>

        {/* GitHub token */}
        <div className="token-section">
          <button
            type="button"
            onClick={() => setShowToken((v) => !v)}
            className="input-label"
            style={{ textAlign: 'left', cursor: 'pointer', color: 'var(--text-accent)' }}
          >
            {showToken ? '▾' : '▸'} GitHub Token (optional but recommended)
          </button>

          {showToken && (
            <div className="input-group" style={{ marginTop: 6 }}>
              <input
                id="github-token-input"
                className="input-field mono"
                type="password"
                placeholder="ghp_xxxxxxxxxxxxxxxxxxxx"
                value={githubToken}
                onChange={(e) => setGithubToken(e.target.value)}
              />
              <div className={`token-status ${githubToken ? 'set' : 'unset'}`}>
                {githubToken
                  ? '🔑 Token saved in browser (localStorage)'
                  : '⚠️ No token — limited to 60 req/hr'}
              </div>
            </div>
          )}
        </div>

        {/* LM Studio AI Local Server Settings */}
        <AISettingsPanel />

        {/* Actions */}
        <div className="flex gap-2">
          <button
            id="analyze-btn"
            type="submit"
            className="btn btn-primary w-full"
            disabled={isAnalyzing || !repoUrl.trim()}
          >
            {isAnalyzing
              ? <><span className="spinner" /> Analyzing…</>
              : '⚡ Analyze Repository'
            }
          </button>
          {isAnalyzing && (
            <button
              id="cancel-btn"
              type="button"
              className="btn btn-secondary"
              onClick={handleCancel}
              style={{ flexShrink: 0 }}
            >
              ✕
            </button>
          )}
        </div>
      </form>

      {/* Progress panel */}
      {analysisStatus && analysisStatus !== null && (
        <div className="progress-panel">
          <div className="progress-header">
            {isAnalyzing && <span className="spinner" />}
            <span style={{ color: statusColor, textTransform: 'capitalize' }}>
              {analysisStatus}
            </span>
          </div>

          <div className="progress-bar-track">
            <div
              className="progress-bar-fill"
              style={{
                width: `${Math.round((analysisProgress || 0) * 100)}%`,
                background: analysisStatus === 'error'
                  ? 'var(--accent-red)'
                  : undefined,
              }}
            />
          </div>

          <p className="progress-message">
            {analysisError || analysisMessage}
          </p>
        </div>
      )}

      {/* Hint */}
      <p style={{ fontSize: 10, color: 'var(--text-muted)', lineHeight: 1.6 }}>
        Supports any public GitHub repo. Endpoints are detected via static
        analysis of config files and source patterns.
      </p>
    </div>
  );
}
