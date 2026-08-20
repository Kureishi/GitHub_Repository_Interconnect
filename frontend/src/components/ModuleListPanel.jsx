/**
 * ModuleListPanel — shows all analyzed modules in the sidebar
 * with delete and focus-on-canvas actions.
 */
import useModuleStore from '../store/useModuleStore';
import LicenseBadge from './LicenseBadge';
import { useReactFlow } from '@xyflow/react';

export default function ModuleListPanel() {
  const { modules, removeModule, showToast } = useModuleStore();
  const { fitView, setCenter } = useReactFlow();

  const moduleList = Object.values(modules);

  const handleFocus = (mod) => {
    setCenter(mod.position_x + 140, mod.position_y + 100, { zoom: 1.2, duration: 400 });
  };

  const handleDelete = async (mod) => {
    await removeModule(mod.id);
    showToast(`Removed ${mod.full_name}`, 'info');
  };

  if (moduleList.length === 0) return null;

  return (
    <div>
      <p className="section-label">Modules ({moduleList.length})</p>
      <div className="module-list">
        {moduleList.map((mod) => (
          <div
            key={mod.id}
            className="module-list-item"
            onClick={() => handleFocus(mod)}
            title="Click to focus on canvas"
          >
            <div className="module-list-repo">
              <div className="module-list-name">{mod.full_name}</div>
              <div className="module-list-lang flex gap-2 items-center" style={{ marginTop: 3 }}>
                {mod.language && <span>{mod.language}</span>}
                <LicenseBadge
                  compatibility={mod.license?.compatibility || 'unknown'}
                  name={mod.license?.name}
                />
              </div>
            </div>
            <button
              className="module-list-delete"
              title="Remove module"
              onClick={(e) => { e.stopPropagation(); handleDelete(mod); }}
              id={`delete-module-${mod.id}`}
            >
              ✕
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
