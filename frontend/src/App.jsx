/**
 * App.jsx — root component.
 * Orchestrates the sidebar and the React Flow canvas.
 */
import { useEffect, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  BackgroundVariant,
  useReactFlow,
  ReactFlowProvider,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import useModuleStore from './store/useModuleStore';
import ModuleNode from './components/ModuleNode';
import AddRepoPanel from './components/AddRepoPanel';
import ModuleListPanel from './components/ModuleListPanel';
import ConnectionPanel from './components/ConnectionPanel';
import AIInferPanel from './components/AIInferPanel';
import FlowReportPanel from './components/FlowReportPanel';

const nodeTypes = { moduleNode: ModuleNode };

// ─────────────────────────────────────────────────────────────
// Flow canvas (needs to be inside ReactFlowProvider)
// ─────────────────────────────────────────────────────────────
function FlowCanvas() {
  const {
    nodes, edges,
    onNodesChange, onEdgesChange, onConnect,
    selectEdge, deselectEdge,
    modules,
  } = useModuleStore();

  const { fitView } = useReactFlow();

  // Fit view when first module added
  useEffect(() => {
    if (Object.keys(modules).length > 0) {
      setTimeout(() => fitView({ padding: 0.2, duration: 400 }), 100);
    }
  }, [Object.keys(modules).length === 1]); // only on first module

  const handleEdgeClick = useCallback((_ev, edge) => {
    selectEdge(edge.id);
  }, [selectEdge]);

  const handlePaneClick = useCallback(() => {
    deselectEdge();
  }, [deselectEdge]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      onNodesChange={onNodesChange}
      onEdgesChange={onEdgesChange}
      onConnect={onConnect}
      onEdgeClick={handleEdgeClick}
      onPaneClick={handlePaneClick}
      nodeTypes={nodeTypes}
      fitView
      fitViewOptions={{ padding: 0.3 }}
      minZoom={0.2}
      maxZoom={2}
      deleteKeyCode="Delete"
      proOptions={{ hideAttribution: true }}
    >
      <Background
        variant={BackgroundVariant.Dots}
        gap={24}
        size={1}
        color="rgba(79,122,255,0.15)"
      />
      <Controls />
      <MiniMap
        nodeColor={(n) => {
          const mod = n.data?.module;
          if (!mod) return '#1c2333';
          const compat = mod.license?.compatibility;
          if (compat === 'permissive') return '#27e39f';
          if (compat === 'copyleft_strong') return '#ff8c42';
          if (compat === 'proprietary') return '#ff4f6d';
          if (compat === 'unknown') return '#526080';
          return '#4f7aff';
        }}
        style={{ background: '#161b27' }}
        maskColor="rgba(8,11,20,0.6)"
      />
    </ReactFlow>
  );
}

// ─────────────────────────────────────────────────────────────
// Toolbar component (inside ReactFlowProvider)
// ─────────────────────────────────────────────────────────────
function Toolbar() {
  const { fitView } = useReactFlow();
  const { modules, connections, exportState, importState, openFlowReport, showToast } = useModuleStore();

  const modCount = Object.keys(modules).length;
  const connCount = Object.keys(connections).length;

  const handleExport = () => {
    const data = exportState();
    const json = JSON.stringify(data, null, 2);
    const blob = new Blob([json], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'interconnect-state.json';
    a.click();
    URL.revokeObjectURL(url);
    showToast('State exported!', 'success');
  };

  const handleImport = () => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'application/json';
    input.onchange = async (e) => {
      const file = e.target.files[0];
      if (!file) return;
      try {
        const text = await file.text();
        const data = JSON.parse(text);
        importState(data);
        showToast('State imported!', 'success');
        setTimeout(() => fitView({ padding: 0.2, duration: 400 }), 100);
      } catch (err) {
        showToast('Import failed: invalid JSON', 'error');
      }
    };
    input.click();
  };

  return (
    <div className="canvas-toolbar">
      <span style={{ fontSize: 11, color: 'var(--text-muted)', paddingRight: 4 }}>
        {modCount} module{modCount !== 1 ? 's' : ''} · {connCount} connection{connCount !== 1 ? 's' : ''}
      </span>
      <div className="toolbar-divider" />
      <button
        id="report-btn"
        className="toolbar-btn text-indigo-300 hover:text-indigo-200 border border-indigo-500/30 bg-indigo-500/10"
        onClick={openFlowReport}
        title="Generate AI Architecture & Pipeline Report"
      >
        ✨ AI Report
      </button>
      <div className="toolbar-divider" />
      <button
        id="fit-view-btn"
        className="toolbar-btn"
        onClick={() => fitView({ padding: 0.2, duration: 400 })}
        title="Fit all modules in view"
      >
        ⊡ Fit
      </button>
      <button
        id="export-btn"
        className="toolbar-btn"
        onClick={handleExport}
        title="Export state as JSON"
      >
        ↑ Export
      </button>
      <button
        id="import-btn"
        className="toolbar-btn"
        onClick={handleImport}
        title="Import state from JSON"
      >
        ↓ Import
      </button>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Toast container
// ─────────────────────────────────────────────────────────────
function ToastContainer() {
  const { toasts } = useModuleStore();
  return (
    <div className="toast-container">
      {toasts.map((t) => (
        <div key={t.id} className={`toast ${t.type}`}>
          {t.message}
        </div>
      ))}
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Empty canvas hint
// ─────────────────────────────────────────────────────────────
function EmptyCanvasHint() {
  const { modules } = useModuleStore();
  if (Object.keys(modules).length > 0) return null;
  return (
    <div className="empty-canvas">
      <div className="empty-canvas-icon">⬡</div>
      <div className="empty-canvas-title">No modules yet</div>
      <div className="empty-canvas-sub">
        Add a GitHub repository in the sidebar to begin mapping your module graph.
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────────────────────
// Root App
// ─────────────────────────────────────────────────────────────
export default function App() {
  const { loadFromServer } = useModuleStore();

  // Load persisted state from backend on mount
  useEffect(() => {
    loadFromServer();
  }, []);

  return (
    <ReactFlowProvider>
      <div className="app-layout">
        {/* ── Sidebar ─────────────────────────────────────── */}
        <aside className="sidebar">
          <div className="sidebar-header">
            <div className="sidebar-logo">
              <div className="sidebar-logo-icon">⬡</div>
              <div>
                <h1>Repo Interconnect</h1>
                <p>Module graph builder</p>
              </div>
            </div>
          </div>
          <div className="sidebar-body">
            <AddRepoPanel />
            <ModuleListPanel />
          </div>

          {/* Stats bar */}
          <StatsBar />
        </aside>

        {/* ── Canvas ──────────────────────────────────────── */}
        <main className="canvas-area">
          <Toolbar />
          <EmptyCanvasHint />
          <FlowCanvas />
          <ConnectionPanel />
        </main>
      </div>

      <AIInferPanel />
      <FlowReportPanel />
      <ToastContainer />
    </ReactFlowProvider>
  );
}

function StatsBar() {
  const { modules, connections } = useModuleStore();
  const mods = Object.values(modules);
  const endpointCount = mods.reduce((acc, m) => acc + (m.endpoints?.length || 0), 0);
  const connCount = Object.keys(connections).length;

  return (
    <div className="stats-bar">
      <div className="stat-item">
        <span>Modules</span>
        <span className="stat-value">{mods.length}</span>
      </div>
      <div className="stat-item">
        <span>Endpoints</span>
        <span className="stat-value">{endpointCount}</span>
      </div>
      <div className="stat-item">
        <span>Connections</span>
        <span className="stat-value">{connCount}</span>
      </div>
    </div>
  );
}
