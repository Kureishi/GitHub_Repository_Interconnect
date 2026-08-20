/**
 * EndpointBadge — colored label for each endpoint type.
 */
const EP_META = {
  rest_api:       { icon: '⚡', label: 'REST API' },
  cli:            { icon: '⌨️', label: 'CLI' },
  library:        { icon: '📦', label: 'Library' },
  data_file:      { icon: '🗄️', label: 'Data' },
  data_structure: { icon: '🧩', label: 'Schema' },
  docker:         { icon: '🐳', label: 'Docker' },
  ml_model:       { icon: '🤖', label: 'ML Model' },
  graphql:        { icon: '◈',  label: 'GraphQL' },
  grpc:           { icon: '↯',  label: 'gRPC' },
  unknown:        { icon: '?',  label: 'Unknown' },
};

export default function EndpointBadge({ type }) {
  const meta = EP_META[type] || EP_META.unknown;
  return (
    <span className={`ep-badge ${type}`} title={meta.label}>
      <span>{meta.icon}</span>
      {meta.label}
    </span>
  );
}
