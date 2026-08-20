/**
 * LicenseBadge — colored badge showing license compatibility level.
 */
const LIC_META = {
  permissive:       { icon: '✅', label: 'Permissive' },
  copyleft_weak:    { icon: '⚠️', label: 'Weak Copyleft' },
  copyleft_strong:  { icon: '⚠️', label: 'Copyleft' },
  proprietary:      { icon: '🔒', label: 'Proprietary' },
  unknown:          { icon: '❓', label: 'No License' },
};

export default function LicenseBadge({ compatibility, name }) {
  const meta = LIC_META[compatibility] || LIC_META.unknown;
  const displayName = name && name !== 'No license detected' ? name : meta.label;
  return (
    <span
      className={`lic-badge ${compatibility}`}
      title={`License: ${displayName}`}
    >
      <span>{meta.icon}</span>
      {displayName.length > 18 ? meta.label : displayName}
    </span>
  );
}
