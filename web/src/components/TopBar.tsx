/**
 * Top navigation bar component
 */

import type { AppConfig } from '../types';
import { ThemeToggle } from './ThemeToggle';

interface TopBarProps {
  config: AppConfig | null;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
}

export function TopBar({ config, theme, onToggleTheme }: TopBarProps) {
  const leftLogo = config?.branding?.headerLeftLogo;
  const rightLogo = config?.branding?.headerRightLogo;
  const title = config?.title || 'Zarrcade';

  return (
    <nav className="top-bar">
      <div className="top-bar-left">
        {leftLogo && (
          <img src={leftLogo} alt="Logo" className="top-bar-logo" />
        )}
      </div>
      <div className="top-bar-center">
        <h1>{title}</h1>
      </div>
      <div className="top-bar-right">
        <ThemeToggle theme={theme} onToggle={onToggleTheme} />
        {rightLogo && (
          <img src={rightLogo} alt="Logo" className="top-bar-logo" />
        )}
      </div>
    </nav>
  );
}
