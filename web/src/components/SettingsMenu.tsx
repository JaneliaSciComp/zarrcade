/**
 * Settings dropdown menu in the top bar.
 *
 * Houses chrome-level controls (theme toggle, About link) so the top bar's
 * right side stays uncluttered. Closes on outside click, Escape, or selection.
 */

import { useEffect, useId, useRef, useState } from 'react';

interface SettingsMenuProps {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export function SettingsMenu({ theme, onToggleTheme }: SettingsMenuProps) {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const menuId = useId();

  useEffect(() => {
    if (!open) return;

    const handlePointer = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };

    document.addEventListener('mousedown', handlePointer);
    document.addEventListener('keydown', handleKey);
    return () => {
      document.removeEventListener('mousedown', handlePointer);
      document.removeEventListener('keydown', handleKey);
    };
  }, [open]);

  const handleToggleTheme = () => {
    onToggleTheme();
    setOpen(false);
  };

  return (
    <div className="settings-menu" ref={containerRef}>
      <button
        type="button"
        className="settings-menu-trigger"
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={menuId}
        aria-label="Settings"
        title="Settings"
        onClick={() => setOpen((o) => !o)}
      >
        <i className="fa-solid fa-ellipsis-vertical" />
      </button>

      {open && (
        <div id={menuId} role="menu" className="settings-menu-panel">
          <button
            type="button"
            role="menuitem"
            className="settings-menu-item"
            onClick={handleToggleTheme}
          >
            <i className={theme === 'light' ? 'fa-regular fa-moon' : 'fa-regular fa-sun'} />
            <span>{theme === 'light' ? 'Switch to dark mode' : 'Switch to light mode'}</span>
          </button>

          <a
            role="menuitem"
            className="settings-menu-item"
            href="https://github.com/JaneliaSciComp/zarrcade"
            target="_blank"
            rel="noopener noreferrer"
            onClick={() => setOpen(false)}
          >
            <i className="fa-brands fa-github" />
            <span>About Zarrcade</span>
          </a>
        </div>
      )}
    </div>
  );
}
