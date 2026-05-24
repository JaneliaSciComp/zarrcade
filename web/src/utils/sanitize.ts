/**
 * HTML sanitization helpers for the two places we render trusted-looking
 * (but potentially attacker-controlled) markup via dangerouslySetInnerHTML.
 *
 * Configs are loaded via ?config=<url>, so any string sourced from a config
 * — or from a CSV referenced by one — must be treated as untrusted.
 */

import DOMPurify from 'dompurify';

/**
 * Strict sanitizer for image card / detail-page titles built from
 * display.titleTemplate. Allows only the small set of formatting tags
 * existing sites use (<font color=...>, basic emphasis); strips scripts,
 * event handlers, anchors, images, and everything else.
 */
export function sanitizeTitle(html: string): string {
  return DOMPurify.sanitize(html, {
    ALLOWED_TAGS: ['font', 'b', 'i', 'em', 'strong', 'span', 'br', 'sub', 'sup'],
    ALLOWED_ATTR: ['color', 'style'],
  });
}

/**
 * Permissive sanitizer for branding HTML slots (footer.left, footer.right,
 * etc.) where authors expect to write a small fragment of mixed content
 * including links. Uses DOMPurify defaults — which strip <script>, event
 * handlers, javascript: URLs, and other XSS vectors — and ensures every
 * <a> opens in a new tab with rel=noopener.
 */
export function sanitizeHtml(html: string): string {
  const clean = DOMPurify.sanitize(html, {
    ADD_ATTR: ['target', 'rel'],
  });
  return clean;
}

/**
 * Reduce an HTML title fragment to plain text, suitable for use in an
 * <img alt> attribute or anywhere else that expects no markup. Scripts and
 * similarly dangerous nodes are dropped entirely (rather than letting their
 * content leak through) so the result is safe to put in any attribute.
 */
export function stripTags(html: string): string {
  return DOMPurify.sanitize(html, { ALLOWED_TAGS: [], ALLOWED_ATTR: [] });
}

// Force external links opened from sanitized HTML to be safe by default.
// DOMPurify lets us hook into the parse pipeline to tweak nodes before
// serialization.
DOMPurify.addHook('afterSanitizeAttributes', (node) => {
  if (node.tagName === 'A' && node instanceof HTMLAnchorElement) {
    node.setAttribute('target', '_blank');
    node.setAttribute('rel', 'noopener noreferrer');
  }
});
