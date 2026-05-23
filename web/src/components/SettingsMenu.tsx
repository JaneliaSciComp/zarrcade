/**
 * Settings dropdown menu in the top bar.
 *
 * Houses chrome-level controls (theme toggle, About link) so the top bar's
 * right side stays uncluttered. Closes on outside click, Escape, or selection.
 */

import { useEffect, useId, useRef, useState, type ReactNode } from 'react';

export type SettingsMenuItem = {
  label: ReactNode;
  icon: string; // Font Awesome class string, e.g. "fa-solid fa-download"
} & ({ onClick: () => void } | { href: string });

interface SettingsMenuProps {
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  /** Custom items rendered at the top of the menu, above the built-in items. */
  extraItems?: SettingsMenuItem[];
}

export function SettingsMenu({ theme, onToggleTheme, extraItems }: SettingsMenuProps) {
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
          {extraItems?.map((item, i) => {
            const inner = (
              <>
                <i className={item.icon} />
                <span>{item.label}</span>
              </>
            );
            return 'href' in item ? (
              <a
                key={i}
                role="menuitem"
                className="settings-menu-item"
                href={item.href}
                target="_blank"
                rel="noopener noreferrer"
                onClick={() => setOpen(false)}
              >
                {inner}
              </a>
            ) : (
              <button
                key={i}
                type="button"
                role="menuitem"
                className="settings-menu-item"
                onClick={() => {
                  item.onClick();
                  setOpen(false);
                }}
              >
                {inner}
              </button>
            );
          })}
          {extraItems && extraItems.length > 0 && <hr className="settings-menu-sep" />}

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
