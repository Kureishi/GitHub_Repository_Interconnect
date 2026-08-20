/**
 * Zustand store — global state for modules, connections, and UI state.
 */
import { create } from 'zustand';
import { applyNodeChanges, applyEdgeChanges } from '@xyflow/react';
import api from '../api/client';

const useModuleStore = create((set, get) => ({
  // ── Data ──────────────────────────────────────────────────────────────────
  modules: {},        // id → Module object
  connections: {},    // id → Connection object

  // React Flow state
  nodes: [],          // RF node objects derived from modules
  edges: [],          // RF edge objects derived from connections

  // ── UI state ──────────────────────────────────────────────────────────────
  analysisStatus: null,   // null | 'pending' | 'fetching' | 'analyzing' | 'done' | 'error'
  analysisProgress: 0,    // 0–1
  analysisMessage: '',
  analysisError: null,

  selectedEdgeId: null,
  githubToken: localStorage.getItem('githubToken') || '',
  toasts: [],

  // ── AI / LM Studio state ───────────────────────────────────────────────────
  lmStudioUrl: localStorage.getItem('lmStudioUrl') || 'http://localhost:1234',
  lmStudioModel: localStorage.getItem('lmStudioModel') || '',
  activeAIInferModuleId: null,
  isFlowReportOpen: false,

  // ── Helpers ───────────────────────────────────────────────────────────────

  /** Convert a Module into a React Flow node */
  _moduleToNode: (mod, isNew = false) => ({
    id: mod.id,
    type: 'moduleNode',
    position: { x: mod.position_x, y: mod.position_y },
    data: { module: mod, isNew },
    dragHandle: '.module-node-header',
  }),

  /** Convert a Connection into a React Flow edge */
  _connToEdge: (conn) => ({
    id: conn.id,
    source: conn.source_module_id,
    target: conn.target_module_id,
    sourceHandle: conn.source_endpoint_id,
    targetHandle: conn.target_endpoint_id,
    label: conn.label || undefined,
    type: 'smoothstep',
    animated: true,
    style: { stroke: '#4f7aff', strokeWidth: 2 },
    markerEnd: { type: 'arrowclosed', color: '#4f7aff' },
    data: { connection: conn },
  }),

  // ── Module actions ─────────────────────────────────────────────────────────

  addModule: (mod) => {
    set((state) => {
      const modules = { ...state.modules, [mod.id]: mod };
      const node = get()._moduleToNode(mod, true);

      // Stagger initial position if overlapping
      const nodeCount = state.nodes.length;
      node.position = {
        x: 120 + (nodeCount % 3) * 320,
        y: 80 + Math.floor(nodeCount / 3) * 350,
      };

      return {
        modules,
        nodes: [...state.nodes.filter(n => n.id !== mod.id), node],
      };
    });
  },

  updateModule: (mod) => {
    set((state) => {
      const modules = { ...state.modules, [mod.id]: mod };
      const currentPos = state.nodes.find((n) => n.id === mod.id)?.position || {
        x: mod.position_x,
        y: mod.position_y,
      };
      const node = {
        ...get()._moduleToNode(mod),
        position: currentPos,
      };
      return {
        modules,
        nodes: state.nodes.map((n) => (n.id === mod.id ? node : n)),
      };
    });
  },

  mergeAIEndpoints: (moduleId, newEndpoints) => {
    const mod = get().modules[moduleId];
    if (!mod) return;
    const existingNames = new Set(mod.endpoints.map((e) => e.name));
    const toAdd = newEndpoints.filter((e) => !existingNames.has(e.name));
    const updated = {
      ...mod,
      endpoints: [...mod.endpoints, ...toAdd],
    };
    get().updateModule(updated);
  },

  removeModule: async (moduleId) => {
    try {
      await api.delete(`/api/modules/${moduleId}`);
    } catch (e) {
      // If already gone server-side, still clean up locally
    }
    set((state) => {
      const modules = { ...state.modules };
      delete modules[moduleId];

      const connections = { ...state.connections };
      Object.keys(connections).forEach((cid) => {
        const c = connections[cid];
        if (c.source_module_id === moduleId || c.target_module_id === moduleId) {
          delete connections[cid];
        }
      });

      return {
        modules,
        connections,
        nodes: state.nodes.filter((n) => n.id !== moduleId),
        edges: state.edges.filter(
          (e) => e.source !== moduleId && e.target !== moduleId
        ),
        selectedEdgeId: state.selectedEdgeId &&
          (state.connections[state.selectedEdgeId]?.source_module_id === moduleId ||
           state.connections[state.selectedEdgeId]?.target_module_id === moduleId)
          ? null : state.selectedEdgeId,
      };
    });
  },

  // ── Connection actions ─────────────────────────────────────────────────────

  addConnection: async (connection) => {
    try {
      const created = await api.post('/api/connections', connection);
      const conn = created.data;
      const edge = get()._connToEdge(conn);
      set((state) => ({
        connections: { ...state.connections, [conn.id]: conn },
        edges: [...state.edges.filter(e => e.id !== conn.id), edge],
      }));
      return conn;
    } catch (e) {
      get().showToast('Failed to save connection: ' + (e.message || ''), 'error');
      return null;
    }
  },

  removeConnection: async (connectionId) => {
    try {
      await api.delete(`/api/connections/${connectionId}`);
    } catch (e) { /* ignore */ }
    set((state) => {
      const connections = { ...state.connections };
      delete connections[connectionId];
      return {
        connections,
        edges: state.edges.filter((e) => e.id !== connectionId),
        selectedEdgeId: state.selectedEdgeId === connectionId ? null : state.selectedEdgeId,
      };
    });
  },

  selectEdge: (edgeId) => set({ selectedEdgeId: edgeId }),
  deselectEdge: () => set({ selectedEdgeId: null }),

  // ── React Flow change handlers ─────────────────────────────────────────────

  onNodesChange: (changes) => {
    set((state) => ({ nodes: applyNodeChanges(changes, state.nodes) }));

    // Persist position changes to backend
    changes.forEach((change) => {
      if (change.type === 'position' && !change.dragging && change.position) {
        api.post(`/api/modules/${change.id}/position`, change.position).catch(() => {});
      }
    });
  },

  onEdgesChange: (changes) => {
    set((state) => ({ edges: applyEdgeChanges(changes, state.edges) }));
  },

  onConnect: async (params) => {
    // params: { source, target, sourceHandle, targetHandle }
    const { v4: uuidv4 } = await import('uuid');
    const connection = {
      id: uuidv4(),
      source_module_id: params.source,
      source_endpoint_id: params.sourceHandle || 'default',
      target_module_id: params.target,
      target_endpoint_id: params.targetHandle || 'default',
      label: '',
    };
    await get().addConnection(connection);
  },

  // ── Analysis actions ───────────────────────────────────────────────────────

  setAnalysisState: (updates) => set(updates),

  // ── GitHub token ──────────────────────────────────────────────────────────

  setGithubToken: (token) => {
    localStorage.setItem('githubToken', token);
    set({ githubToken: token });
  },

  // ── AI actions ─────────────────────────────────────────────────────────────

  setLMStudioUrl: (url) => {
    localStorage.setItem('lmStudioUrl', url);
    set({ lmStudioUrl: url });
  },

  setLMStudioModel: (model) => {
    localStorage.setItem('lmStudioModel', model);
    set({ lmStudioModel: model });
  },

  openAIInfer: (moduleId) => set({ activeAIInferModuleId: moduleId }),
  closeAIInfer: () => set({ activeAIInferModuleId: null }),

  openFlowReport: () => set({ isFlowReportOpen: true }),
  closeFlowReport: () => set({ isFlowReportOpen: false }),

  // ── Toast notifications ────────────────────────────────────────────────────

  showToast: (message, type = 'info') => {
    const id = Date.now();
    set((state) => ({
      toasts: [...state.toasts, { id, message, type }],
    }));
    setTimeout(() => {
      set((state) => ({
        toasts: state.toasts.filter((t) => t.id !== id),
      }));
    }, 4000);
  },

  // ── Import / Export ────────────────────────────────────────────────────────

  exportState: () => {
    const state = get();
    return {
      modules: Object.values(state.modules),
      connections: Object.values(state.connections),
    };
  },

  importState: (appState) => {
    const modules = {};
    const connections = {};
    appState.modules?.forEach((m) => { modules[m.id] = m; });
    appState.connections?.forEach((c) => { connections[c.id] = c; });

    const nodes = Object.values(modules).map((m) => get()._moduleToNode(m));
    const edges = Object.values(connections).map((c) => get()._connToEdge(c));

    set({ modules, connections, nodes, edges });
  },

  // ── Load from server ───────────────────────────────────────────────────────

  loadFromServer: async () => {
    try {
      const res = await api.get('/api/state');
      get().importState(res.data);
    } catch (e) {
      // Backend might not be up yet, ignore
    }
  },
}));

export default useModuleStore;
