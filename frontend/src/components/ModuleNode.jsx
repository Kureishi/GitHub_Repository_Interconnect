/**
 * ModuleNode — custom React Flow node representing an analyzed GitHub module.
 *
 * Left handles  = input endpoints (what the module can consume)
 * Right handles = output endpoints (what the module exposes)
 */
import { memo, useEffect, useRef } from 'react';
import { Handle, Position } from '@xyflow/react';
import EndpointBadge from './EndpointBadge';
import LicenseBadge from './LicenseBadge';
import useModuleStore from '../store/useModuleStore';

function ModuleNode({ data, selected }) {
  const { module, isNew } = data;
  const nodeRef = useRef(null);
  const openAIInfer = useModuleStore((s) => s.openAIInfer);

  // Pulse animation when first added
  useEffect(() => {
    if (isNew && nodeRef.current) {
      nodeRef.current.classList.add('new-pulse');
      const t = setTimeout(() => nodeRef.current?.classList.remove('new-pulse'), 700);
      return () => clearTimeout(t);
    }
  }, [isNew]);

  const hasWarning =
    module.caution_notes?.length > 0 ||
    module.license?.compatibility === 'copyleft_strong' ||
    module.license?.compatibility === 'proprietary' ||
    module.license?.compatibility === 'unknown';

  return (
    <div
      ref={nodeRef}
      className={[
        'module-node',
        selected ? 'selected' : '',
        hasWarning ? 'has-warning' : '',
      ].join(' ')}
    >
      {/* ── Header ──────────────────────────────────────────── */}
      <div className="module-node-header">
        <div className="module-node-title-row">
          <span className="module-node-name">
            {module.owner}/<strong>{module.repo_name}</strong>
          </span>
          <div className="flex items-center gap-1.5 nodrag">
            <button
              onClick={(e) => {
                e.stopPropagation();
                openAIInfer(module.id);
              }}
              onMouseDown={(e) => e.stopPropagation()}
              className="nodrag nopan text-[11px] bg-indigo-500/20 hover:bg-indigo-500/30 text-indigo-300 border border-indigo-500/40 px-2 py-0.5 rounded transition-colors flex items-center gap-1 cursor-pointer"
              title="Analyze or infer endpoints with local LLM"
            >
              <span>✨</span>
              <span>AI</span>
            </button>
            <span className="module-node-stars">
              ⭐ {(module.stars || 0).toLocaleString()}
            </span>
          </div>
        </div>

        {module.description && (
          <p className="module-node-desc">{module.description}</p>
        )}

        <div className="module-node-meta">
          {module.language && (
            <span style={{ fontSize: 10, color: 'var(--text-muted)', background: 'var(--bg-elevated)', padding: '2px 6px', borderRadius: 4, border: '1px solid var(--border-subtle)' }}>
              {module.language}
            </span>
          )}
          <LicenseBadge
            compatibility={module.license?.compatibility || 'unknown'}
            name={module.license?.name}
          />
        </div>
      </div>

      {/* ── Caution note ────────────────────────────────────── */}
      {module.caution_notes?.length > 0 && (
        <div className="module-node-warning">
          {module.caution_notes[0]}
        </div>
      )}

      {/* ── Endpoints ───────────────────────────────────────── */}
      {module.endpoints?.length > 0 && (
        <div className="module-node-endpoints">
          {module.endpoints.map((ep) => (
            <div key={ep.id} className="endpoint-row">
              {/* Input handle on the left */}
              <Handle
                id={`${ep.id}-in`}
                type="target"
                position={Position.Left}
                title={`Input Port: Drop connection here to send data into '${ep.name}'`}
              />

              <div className="endpoint-row-left">
                <EndpointBadge type={ep.type} />
                <span className="endpoint-row-name" title={ep.description || ep.name}>
                  {ep.name}
                </span>
                {ep.source === 'ai' && (
                  <span
                    className="ml-1 text-[10px] text-indigo-400 bg-indigo-500/20 px-1 rounded font-mono"
                    title="Inferred by AI"
                  >
                    ✨
                  </span>
                )}
              </div>

              {/* Visual port badge */}
              <div className="flex items-center gap-1">
                <span
                  className="endpoint-port-badge output"
                  title="Drag from right handle to wire this endpoint to another module"
                >
                  out ➔
                </span>
              </div>

              {/* Output handle on the right */}
              <Handle
                id={`${ep.id}-out`}
                type="source"
                position={Position.Right}
                title={`Output Port: Drag to wire '${ep.name}' to another module`}
              />
            </div>
          ))}
        </div>
      )}

      {module.endpoints?.length === 0 && (
        <div style={{ padding: '10px 16px', fontSize: 11, color: 'var(--text-muted)', fontStyle: 'italic' }}>
          No endpoints detected
        </div>
      )}

      {/* Default handles when no endpoints */}
      {module.endpoints?.length === 0 && (
        <>
          <Handle id="default-in" type="target" position={Position.Left} />
          <Handle id="default-out" type="source" position={Position.Right} />
        </>
      )}

      {/* Repo link */}
      <div style={{
        padding: '6px 14px',
        borderTop: '1px solid var(--border-subtle)',
        background: 'rgba(0,0,0,.2)',
        display: 'flex',
        justifyContent: 'flex-end',
      }}>
        <a
          href={module.repo_url}
          target="_blank"
          rel="noopener noreferrer"
          style={{ fontSize: 10, color: 'var(--text-accent)' }}
          onClick={(e) => e.stopPropagation()}
        >
          View on GitHub ↗
        </a>
      </div>
    </div>
  );
}

export default memo(ModuleNode);
