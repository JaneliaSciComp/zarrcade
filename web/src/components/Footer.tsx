/**
 * Footer component
 */

import type { AppConfig } from '../types';

interface FooterProps {
  config: AppConfig | null;
}

export function Footer({ config }: FooterProps) {
  const links = config?.branding?.footerLinks || [];

  return (
    <footer className="footer">
      <div className="footer-content">
        <span>
          <a href="https://github.com/JaneliaSciComp/zarrcade" target="_blank" rel="noopener noreferrer" style={{ color: 'white', textDecoration: 'none' }}>
            <i className="fa-brands fa-github" style={{ fontSize: '1.5rem', marginRight: '0.5rem' }} /><span style={{ position: 'relative', top: '-1px' }}>Made with Zarrcade</span>
          </a>
        </span>
        {links.length > 0 && (
          <div className="footer-links">
            {links.map((link, index) => (
              <a
                key={index}
                href={link.url}
                target="_blank"
                rel="noopener noreferrer"
              >
                {link.label}
              </a>
            ))}
          </div>
        )}
      </div>
    </footer>
  );
}
