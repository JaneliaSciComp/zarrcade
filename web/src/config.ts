/**
 * Configuration loading for Zarrcade SPA
 */

import type { AppConfig, Viewer } from './types';

const DEFAULT_VIEWERS: Viewer[] = [
  {
    name: 'Neuroglancer',
    icon: 'neuroglancer.png',
    urlTemplate: 'https://neuroglancer-demo.appspot.com/#!{URL}',
    enabled: true,
  },
  {
    name: 'Avivator',
    icon: 'vizarr_logo.png',
    urlTemplate: 'https://janeliascicomp.github.io/viv/?image_url={URL}',
    enabled: true,
  },
  {
    name: 'OME-NGFF Validator',
    icon: 'check.png',
    urlTemplate: 'https://ome.github.io/ome-ngff-validator/?source={URL}',
    enabled: false,
  },
  {
    name: 'Vol-E',
    icon: 'aics_website-3d-cell-viewer.png',
    urlTemplate: 'https://volumeviewer.allencell.org/viewer?url={URL}',
    enabled: false,
  },
  {
    name: 'BioNGFF',
    icon: 'vizarr_logo.png',
    urlTemplate: 'https://biongff.github.io/biongff-viewer/?source={URL}',
    enabled: false,
  },
];

const DEFAULT_CONFIG: Partial<AppConfig> = {
  title: 'Zarrcade',
  data: {
    delimiter: ',',
    pathColumn: 'path',
  },
  display: {
    pageSize: 50,
  },
  viewers: DEFAULT_VIEWERS,
};

/**
 * Load configuration from various sources
 * Priority: URL param > /config.json > defaults
 */
export async function loadConfig(): Promise<AppConfig> {
  // Check for config URL in query params
  const urlParams = new URLSearchParams(window.location.search);
  const configUrl = urlParams.get('config');

  let config: Partial<AppConfig> = {};

  if (configUrl) {
    // Load from URL parameter
    try {
      const response = await fetch(configUrl);
      if (response.ok) {
        config = await response.json();
      }
    } catch (e) {
      console.warn('Failed to load config from URL param:', e);
    }
  } else {
    // Try to load from /config.json
    try {
      const response = await fetch('./config.json');
      if (response.ok) {
        config = await response.json();
      }
    } catch (e) {
      console.warn('No config.json found, using defaults');
    }
  }

  // Check for data URL override in query params
  const dataUrl = urlParams.get('data');
  if (dataUrl) {
    config.dataUrl = dataUrl;
  }

  // Merge with defaults
  const mergedConfig: AppConfig = {
    ...DEFAULT_CONFIG,
    ...config,
    data: {
      ...DEFAULT_CONFIG.data,
      ...config.data,
    },
    display: {
      ...DEFAULT_CONFIG.display,
      ...config.display,
    },
    viewers: config.viewers || DEFAULT_CONFIG.viewers,
  } as AppConfig;

  if (!mergedConfig.dataUrl) {
    throw new Error('No data URL configured. Set dataUrl in config.json or use ?data= parameter.');
  }

  return mergedConfig;
}
