import React, { useState, useEffect, useRef } from 'react';
import Markdown from 'react-markdown';
import useModuleStore from '../store/useModuleStore';

export default function FlowReportPanel() {
  const {
    isFlowReportOpen,
    closeFlowReport,
    modules,
    connections,
    lmStudioUrl,
    lmStudioModel,
    showToast,
  } = useModuleStore();

  const [reportMarkdown, setReportMarkdown] = useState('');
  const [isGenerating, setIsGenerating] = useState(false);
  const [error, setError] = useState(null);
  const wsRef = useRef(null);

  const moduleList = Object.values(modules);
  const connectionList = Object.values(connections);

  const startReport = () => {
    if (moduleList.length === 0) {
      showToast('Add some modules to the canvas before generating a report.', 'info');
      return;
    }

    setIsGenerating(true);
    setError(null);
    setReportMarkdown('');

    const wsProto = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProto}//${window.location.host}/ws/llm/report`;
    const ws = new WebSocket(wsUrl);
    wsRef.current = ws;

    ws.onopen = () => {
      ws.send(JSON.stringify({
        lm_url: lmStudioUrl,
        model: lmStudioModel || null,
      }));
    };

    ws.onmessage = (evt) => {
      try {
        const data = JSON.parse(evt.data);
        if (data.type === 'token') {
          setReportMarkdown((prev) => prev + data.text);
        } else if (data.type === 'done') {
          setIsGenerating(false);
          showToast('Architecture report generated successfully!', 'success');
        } else if (data.type === 'error') {
          setError(data.message);
          setIsGenerating(false);
          showToast(`Report error: ${data.message}`, 'error');
        }
      } catch (e) {
        console.error('WS parse error:', e);
      }
    };

    ws.onerror = () => {
      setError('Could not connect to WebSocket. Ensure backend server is running.');
      setIsGenerating(false);
    };

    ws.onclose = () => {
      setIsGenerating(false);
    };
  };

  useEffect(() => {
    if (isFlowReportOpen && !reportMarkdown && !isGenerating) {
      startReport();
    }
    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, [isFlowReportOpen]);

  if (!isFlowReportOpen) return null;

  const exportAsMarkdown = () => {
    const blob = new Blob([reportMarkdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `pipeline_report_${new Date().toISOString().slice(0, 10)}.md`;
    link.click();
    URL.revokeObjectURL(url);
    showToast('Report downloaded as .md file!', 'info');
  };

  const copyToClipboard = () => {
    navigator.clipboard.writeText(reportMarkdown);
    showToast('Report copied to clipboard!', 'success');
  };

  const openInNewWindow = () => {
    const printWindow = window.open('', '_blank');
    if (!printWindow) {
      showToast('Pop-up blocked. Please allow pop-ups for this site.', 'error');
      return;
    }

    const html = `
      <!DOCTYPE html>
      <html>
        <head>
          <title>Pipeline Architecture Report - ${new Date().toISOString().slice(0, 10)}</title>
          <meta charset="utf-8">
          <style>
            body {
              font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
              line-height: 1.6;
              max-width: 860px;
              margin: 40px auto;
              padding: 0 20px;
              color: #1a1a1a;
            }
            h1, h2, h3 { color: #0f172a; }
            h1 { border-bottom: 2px solid #e2e8f0; padding-bottom: 8px; }
            h2 { margin-top: 30px; border-bottom: 1px solid #e2e8f0; padding-bottom: 6px; }
            code { background: #f1f5f9; padding: 2px 5px; border-radius: 4px; font-size: 0.9em; }
            pre { background: #0f172a; color: #f8fafc; padding: 16px; border-radius: 8px; overflow-x: auto; }
            table { width: 100%; border-collapse: collapse; margin: 16px 0; }
            th, td { border: 1px solid #cbd5e1; padding: 8px 12px; text-align: left; }
            th { background: #f8fafc; font-weight: 600; }
            blockquote { border-left: 4px solid #6366f1; margin: 16px 0; padding: 8px 16px; background: #f8fafc; }
            @media print {
              body { margin: 20mm; font-size: 11pt; }
              button { display: none; }
            }
          </style>
        </head>
        <body>
          <div style="display: flex; justify-content: flex-end; margin-bottom: 20px;">
            <button onclick="window.print()" style="padding: 8px 16px; background: #4f46e5; color: white; border: none; border-radius: 6px; cursor: pointer; font-weight: 600;">
              🖨️ Print / Save as PDF
            </button>
          </div>
          <div id="content"></div>
          <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
          <script>
            const md = ${JSON.stringify(reportMarkdown)};
            document.getElementById('content').innerHTML = marked.parse(md);
          </script>
        </body>
      </html>
    `;
    printWindow.document.write(html);
    printWindow.document.close();
    showToast('Report opened in dedicated view / PDF printer window!', 'info');
  };

  return (
    <div className="modal-overlay" onClick={closeFlowReport}>
      <div
        className="modal-dialog modal-lg"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="modal-header">
          <div className="modal-title-group">
            <span style={{ fontSize: 22 }}>📑</span>
            <div>
              <div className="modal-title">
                <span>Pipeline Architecture & Flow Report</span>
                {isGenerating && (
                  <span
                    style={{
                      fontSize: 11,
                      background: 'rgba(155, 114, 255, 0.2)',
                      color: '#c084fc',
                      border: '1px solid rgba(155, 114, 255, 0.4)',
                      padding: '2px 8px',
                      borderRadius: 999,
                      fontWeight: 500,
                    }}
                  >
                    Streaming from local LLM...
                  </span>
                )}
              </div>
              <div className="modal-subtitle">
                {moduleList.length} module(s) · {connectionList.length} connection(s) · Model: <span style={{ color: 'var(--text-accent)' }}>{lmStudioModel || 'default'}</span>
              </div>
            </div>
          </div>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
            {reportMarkdown && !isGenerating && (
              <>
                <button
                  onClick={openInNewWindow}
                  className="btn btn-secondary"
                  style={{ fontSize: 11, padding: '4px 10px' }}
                  title="Open report in a clean separate window to view, export, or print as PDF"
                >
                  📄 Open / Print PDF
                </button>

                <button
                  onClick={exportAsMarkdown}
                  className="btn btn-secondary"
                  style={{ fontSize: 11, padding: '4px 10px' }}
                  title="Download Markdown file"
                >
                  ⬇️ .md
                </button>

                <button
                  onClick={copyToClipboard}
                  className="btn btn-secondary"
                  style={{ fontSize: 11, padding: '4px 10px' }}
                  title="Copy markdown text"
                >
                  📋 Copy
                </button>

                <button
                  onClick={startReport}
                  className="btn btn-secondary"
                  style={{ fontSize: 11, padding: '4px 10px' }}
                  title="Regenerate report"
                >
                  🔄
                </button>
              </>
            )}
            <button
              onClick={closeFlowReport}
              className="modal-close-btn"
              title="Close"
            >
              ✕
            </button>
          </div>
        </div>

        {/* Report Content Body */}
        <div className="modal-body" style={{ background: 'var(--bg-void)' }}>
          {error ? (
            <div
              style={{
                background: 'rgba(255, 79, 109, 0.1)',
                border: '1px solid rgba(255, 79, 109, 0.3)',
                borderRadius: 'var(--r2)',
                padding: 16,
                color: 'var(--accent-red)',
              }}
            >
              <div style={{ fontWeight: 700, marginBottom: 4 }}>Generation Error</div>
              <p style={{ fontSize: 12, fontFamily: 'var(--font-mono)' }}>{error}</p>
              <button
                onClick={startReport}
                className="btn btn-primary"
                style={{ marginTop: 12, fontSize: 11 }}
              >
                Retry
              </button>
            </div>
          ) : reportMarkdown ? (
            <div className="report-content">
              <Markdown>{reportMarkdown}</Markdown>
              {isGenerating && (
                <span
                  style={{
                    display: 'inline-block',
                    width: 8,
                    height: 14,
                    background: 'var(--accent-purple)',
                    marginLeft: 4,
                    verticalAlign: 'middle',
                    animation: 'node-pulse 500ms infinite',
                  }}
                />
              )}
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', height: '100%', padding: '40px 0', color: 'var(--text-muted)' }}>
              <div className="spinner" style={{ width: 28, height: 28, borderWidth: 3, marginBottom: 12 }} />
              <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-primary)' }}>
                Connecting to LM Studio...
              </div>
              <div style={{ fontSize: 11, marginTop: 4 }}>
                Synthesizing module graph architecture and analyzing data flows...
              </div>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="modal-footer">
          <span style={{ fontSize: 11, color: 'var(--text-muted)' }}>
            Report synthesizes full graph topology, endpoint transformations, and license compatibility.
          </span>
          <button
            onClick={closeFlowReport}
            className="btn btn-secondary"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
