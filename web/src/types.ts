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
}

export interface DisplayConfig {
  titleTemplate?: string;
  titleColumn?: string;
  hideColumns?: string[];
  pageSize?: number;
}

export interface BrandingConfig {
  headerLeftLogo?: string;
  headerRightLogo?: string;
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
