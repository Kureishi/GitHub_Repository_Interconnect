/**
 * ConnectionPanel — slide-up panel showing selected edge details.
 */
import useModuleStore from '../store/useModuleStore';
import EndpointBadge from './EndpointBadge';

const COMPAT_LEVELS = {
  permissive:       { cls: 'ok',   label: '✅ Compatible' },
  copyleft_weak:    { cls: 'warn', label: '⚠️ Chainable with caution' },
  copyleft_strong:  { cls: 'warn', label: '⚠️ Copyleft may propagate' },
  proprietary:      { cls: 'error',label: '🔒 Restricted — check license' },
  unknown:          { cls: 'warn', label: '❓ Unknown license — verify first' },
};

function findEndpoint(module, endpointId) {
  if (!module || !endpointId) return null;
  // Strip -in / -out suffix that handles use
  const baseId = endpointId.replace(/-(in|out)$/, '');
  return module.endpoints?.find((ep) => ep.id === baseId || ep.id === endpointId) || null;
}

export default function ConnectionPanel() {
  const { selectedEdgeId, connections, modules, removeConnection } = useModuleStore();

  if (!selectedEdgeId) return null;

  const conn = connections[selectedEdgeId];
  if (!conn) return null;

  const srcMod = modules[conn.source_module_id];
  const tgtMod = modules[conn.target_module_id];
  const srcEp  = findEndpoint(srcMod, conn.source_endpoint_id);
  const tgtEp  = findEndpoint(tgtMod, conn.target_endpoint_id);

  // Worst-case compatibility
  const getCompat = (mod) => mod?.license?.compatibility || 'unknown';
  const srcCompat = getCompat(srcMod);
  const tgtCompat = getCompat(tgtMod);

  const worstCompat = ['proprietary', 'copyleft_strong', 'copyleft_weak', 'unknown', 'permissive']
    .find((c) => srcCompat === c || tgtCompat === c) || 'permissive';

  const compatMeta = COMPAT_LEVELS[worstCompat] || COMPAT_LEVELS.unknown;

  return (
    <div className="connection-panel" id="connection-panel">
      <div className="connection-panel-header">
        <span className="connection-panel-title">🔗 Connection Detail</span>
        <button
          className="btn btn-danger"
          style={{ padding: '3px 10px', fontSize: 11 }}
          onClick={() => removeConnection(selectedEdgeId)}
          id="remove-connection-btn"
        >
          Remove
        </button>
      </div>

      <div className="connection-panel-body">
        {/* Data flow visualization */}
        <div className="connection-flow">
          <div className="connection-flow-node">
            <div className="connection-flow-node-name">
              {srcMod?.repo_name || '?'}
            </div>
            {srcEp && (
              <div className="connection-flow-ep">
                <EndpointBadge type={srcEp.type} />
              </div>
            )}
          </div>

          <span className="connection-arrow">→</span>

          <div className="connection-flow-node">
            <div className="connection-flow-node-name">
              {tgtMod?.repo_name || '?'}
            </div>
            {tgtEp && (
              <div className="connection-flow-ep">
                <EndpointBadge type={tgtEp.type} />
              </div>
            )}
          </div>
        </div>

        {/* Compatibility note */}
        <div className={`connection-compat ${compatMeta.cls}`}>
          <strong>{compatMeta.label}</strong>
          {conn.compatibility_note && (
            <p style={{ marginTop: 4 }}>{conn.compatibility_note}</p>
          )}
          {(srcMod?.license?.chain_warning || tgtMod?.license?.chain_warning) && (
            <p style={{ marginTop: 4, opacity: .85 }}>
              {srcMod?.license?.chain_warning || tgtMod?.license?.chain_warning}
            </p>
          )}
        </div>

        {/* Endpoint details */}
        {(srcEp || tgtEp) && (
          <div style={{ fontSize: 11, color: 'var(--text-secondary)', lineHeight: 1.6 }}>
            {srcEp && <p><strong>Source:</strong> {srcEp.description || srcEp.name}</p>}
            {tgtEp && <p><strong>Target:</strong> {tgtEp.description || tgtEp.name}</p>}
          </div>
        )}
      </div>
    </div>
  );
}
