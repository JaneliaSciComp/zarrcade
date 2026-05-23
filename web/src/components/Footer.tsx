/**
 * Footer component
 */

import type { AppConfig, SlotContent } from '../types';

interface FooterProps {
  config: AppConfig | null;
}

function Slot({ content }: { content?: SlotContent }) {
  if (!content) return null;

  if ('html' in content) {
    return <span dangerouslySetInnerHTML={{ __html: content.html }} />;
  }
  if ('text' in content) {
    return <span>{content.text}</span>;
  }
  // image variant
  const img = <img src={content.image} alt={content.alt ?? ''} className="footer-image" />;
  if (content.href) {
    return (
      <a href={content.href} target="_blank" rel="noopener noreferrer">
        {img}
      </a>
    );
  }
  return img;
}

export function Footer({ config }: FooterProps) {
  const branding = config?.branding;
  const left = branding?.footer?.left;
  const right = branding?.footer?.right;
  const legacyLinks = branding?.footerLinks || [];
  const style = branding?.footerBg ? { background: branding.footerBg } : undefined;

  return (
    <footer className="footer" style={style}>
      <div className="footer-content">
        <div className="footer-side footer-left">
          <Slot content={left} />
          {legacyLinks.length > 0 && (
            <div className="footer-links">
              {legacyLinks.map((link, i) => (
                <a key={i} href={link.url} target="_blank" rel="noopener noreferrer">
                  {link.label}
                </a>
              ))}
            </div>
          )}
        </div>
        <div className="footer-side footer-right">
          <Slot content={right} />
        </div>
      </div>
    </footer>
  );
}
