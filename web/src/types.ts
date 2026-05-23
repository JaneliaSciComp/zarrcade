/**
 * Type definitions for Zarrcade SPA
 */

export interface Viewer {
  name: string;
  icon: string;
  urlTemplate: string;
  enabled: boolean;
}

export interface FilterConfig {
  column: string;
  label: string;
  dataType?: 'string' | 'csv';
}

export interface DataConfig {
  delimiter?: string;
  pathColumn?: string;
  baseUrl?: string;
  thumbnailColumn?: string;
  thumbnailBaseUrl?: string;
  // Optional full-size image shown on the detail page in place of the thumbnail.
  fullSizeColumn?: string;
  fullSizeBaseUrl?: string;
}

export interface DisplayConfig {
  titleTemplate?: string;
  titleColumn?: string;
  hideColumns?: string[];
  pageSize?: number;
}

/**
 * A logo can be specified as a bare URL string (legacy) or as an object with
 * an optional clickable href and accessible alt text.
 */
export type LogoSpec = string | { src: string; href?: string; alt?: string };

/**
 * Content for a named branding slot (e.g. footer.left).
 *  - { html } — rendered via dangerouslySetInnerHTML (configs are author-controlled)
 *  - { text } — rendered as plain text
 *  - { image, href?, alt? } — rendered as an <img>, optionally wrapped in <a>
 */
export type SlotContent =
  | { html: string }
  | { text: string }
  | { image: string; href?: string; alt?: string };

export interface BrandingConfig {
  headerLeftLogo?: LogoSpec;
  headerRightLogo?: LogoSpec;
  /** CSS color applied to the top bar background (e.g. "#000"). */
  headerBg?: string;
  /** CSS color applied to the footer background. */
  footerBg?: string;
  /** Two-column footer slots. */
  footer?: { left?: SlotContent; right?: SlotContent };
  /** Kept for back-compat with older configs. */
  footerLinks?: Array<{ label: string; url: string }>;
}

export interface AppConfig {
  dataUrl: string;
  title?: string;
  data?: DataConfig;
  display?: DisplayConfig;
  filters?: FilterConfig[];
  viewers?: Viewer[];
  branding?: BrandingConfig;
}

export interface ImageRow {
  [key: string]: string | number | undefined;
}

export interface FilterState {
  [column: string]: string;
}
