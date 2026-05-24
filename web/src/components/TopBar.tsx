/**
 * Top navigation bar component
 */

import type { AppConfig, LogoSpec } from '../types';
import { SettingsMenu, type SettingsMenuItem } from './SettingsMenu';

interface TopBarProps {
  config: AppConfig | null;
  theme: 'light' | 'dark';
  onToggleTheme: () => void;
  menuGroups?: SettingsMenuItem[][];
}

function Logo({ spec }: { spec?: LogoSpec }) {
  if (!spec) return null;
  const obj = typeof spec === 'string' ? { src: spec } : spec;
  const img = <img src={obj.src} alt={obj.alt ?? 'Logo'} className="top-bar-logo" />;
  if (obj.href) {
    return (
      <a href={obj.href} target="_blank" rel="noopener noreferrer">
        {img}
      </a>
    );
  }
  return img;
}

export function TopBar({ config, theme, onToggleTheme, menuGroups }: TopBarProps) {
  const branding = config?.branding;
  const title = config?.title || 'Zarrcade';
  const style = branding?.headerBg ? { background: branding.headerBg } : undefined;

  return (
    <nav className="top-bar" style={style}>
      <div className="top-bar-left">
        <Logo spec={branding?.headerLeftLogo} />
      </div>
      <div className="top-bar-center">
        <h1>{title}</h1>
      </div>
      <div className="top-bar-right">
        <Logo spec={branding?.headerRightLogo} />
        <SettingsMenu theme={theme} onToggleTheme={onToggleTheme} extraGroups={menuGroups} />
      </div>
    </nav>
  );
}
