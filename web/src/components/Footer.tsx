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
        <span>Powered by Zarrcade</span>
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
