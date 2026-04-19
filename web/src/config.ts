/**
 * Configuration loading for Zarrcade SPA
 */

import type { AppConfig, Viewer } from './types';

const DEFAULT_VIEWERS: Viewer[] = [
  {
    name: 'Neuroglancer',
    icon: 'neuroglancer.png',
    urlTemplate: "https://neuroglancer-demo.appspot.com/#!{\"layers\":[{\"name\":\"{NAME}\",\"source\":\"{URL}\",\"type\":\"auto\"}],\"selectedLayer\":{\"visible\":true,\"layer\":\"{NAME}\"},\"layout\":\"4panel-alt\"}",
    enabled: true,
  },
  {
    name: 'Avivator',
    icon: 'vizarr_logo.png',
    urlTemplate: 'https://janeliascicomp.github.io/viv/?image_url={ENCODED_URL}',
    enabled: true,
  },
  {
    name: 'OME-NGFF Validator',
    icon: 'check.png',
    urlTemplate: 'https://ome.github.io/ome-ngff-validator/?source={ENCODED_URL}',
    enabled: false,
  },
  {
    name: 'Vol-E',
    icon: 'aics_website-3d-cell-viewer.png',
    urlTemplate: 'https://volumeviewer.allencell.org/viewer?url={ENCODED_URL}',
    enabled: false,
  },
  {
    name: 'BioNGFF',
    icon: 'vizarr_logo.png',
    urlTemplate: 'https://biongff.github.io/biongff-viewer/?source={ENCODED_URL}',
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
 * Runtime-injected config URL. The Docker image substitutes this at container
 * startup from the CONFIG_URL env var; in dev the literal `${CONFIG_URL}`
 * placeholder is left in place and treated as absent.
 */
function getInjectedConfigUrl(): string | null {
  const raw = (window as unknown as { __ZARRCADE_CONFIG_URL__?: string })
    .__ZARRCADE_CONFIG_URL__;
  if (!raw || raw === '${CONFIG_URL}') return null;
  return raw;
}

/**
 * Load configuration from various sources.
 * Priority: `?config=` query param > CONFIG_URL (Docker-injected) >
 *          /config.local.json (dev only) > /config.json > built-in defaults
 */
export async function loadConfig(): Promise<AppConfig | null> {
  const urlParams = new URLSearchParams(window.location.search);
  const configUrl = urlParams.get('config') ?? getInjectedConfigUrl();

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
    // Try config.local.json first (gitignored, for development)
    let loaded = false;
    try {
      const localResponse = await fetch('./config.local.json');
      if (localResponse.ok) {
        config = await localResponse.json();
        loaded = true;
      }
    } catch (e) {
      // config.local.json not found, fall through
    }

    // Fall back to config.json
    if (!loaded) {
      try {
        const response = await fetch('./config.json');
        if (response.ok) {
          config = await response.json();
        }
      } catch (e) {
        console.warn('No config.json found, using defaults');
      }
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
    return null;
  }

  return mergedConfig;
}
