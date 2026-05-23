/**
 * Toggle between gallery and table views.
 */

export type ViewMode = 'gallery' | 'table';

interface ViewToggleProps {
  value: ViewMode;
  onChange: (mode: ViewMode) => void;
}

export function ViewToggle({ value, onChange }: ViewToggleProps) {
  return (
    // No role="group": Pico styles [role="group"] as a full-width flex
    // container with primary-colored child buttons, which both stretched the
    // toggle to 100% and bleached the icons.
    <div className="view-toggle" aria-label="View mode">
      <button
        type="button"
        className={`view-toggle-button ${value === 'gallery' ? 'is-active' : ''}`}
        aria-pressed={value === 'gallery'}
        title="Gallery view"
        onClick={() => onChange('gallery')}
      >
        <i className="fa-solid fa-table-cells-large" />
      </button>
      <button
        type="button"
        className={`view-toggle-button ${value === 'table' ? 'is-active' : ''}`}
        aria-pressed={value === 'table'}
        title="Table view"
        onClick={() => onChange('table')}
      >
        <i className="fa-solid fa-list" />
      </button>
    </div>
  );
}
