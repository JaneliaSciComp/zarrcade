/**
 * Configuration loading for Zarrcade SPA
 */

import type { AppConfig, BrandingConfig, Viewer } from './types';

/**
 * Mutate a BrandingConfig in place, turning every relative asset URL into an
 * absolute URL resolved against the config file's location.
 */
function resolveBrandingAgainst(b: BrandingConfig, base: string): void {
  const resolveStr = (s: string | undefined) =>
    s ? new URL(s, base).href : s;

  const resolveLogo = (logo: BrandingConfig['headerLeftLogo']) => {
    if (!logo) return logo;
    if (typeof logo === 'string') return resolveStr(logo);
    return { ...logo, src: new URL(logo.src, base).href };
  };

  b.headerLeftLogo = resolveLogo(b.headerLeftLogo);
  b.headerRightLogo = resolveLogo(b.headerRightLogo);

  for (const slot of [b.footer?.left, b.footer?.right]) {
    if (slot && 'image' in slot) {
      slot.image = new URL(slot.image, base).href;
    }
  }
}

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
  // The absolute URL of the config file we actually loaded; used to resolve
  // a relative dataUrl against the config's location rather than the app URL.
  let loadedFromUrl: string | null = null;

  if (configUrl) {
    // Load from URL parameter
    try {
      const response = await fetch(configUrl);
      if (response.ok) {
        config = await response.json();
        loadedFromUrl = new URL(configUrl, window.location.href).href;
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
        loadedFromUrl = new URL('./config.local.json', window.location.href).href;
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
          loadedFromUrl = new URL('./config.json', window.location.href).href;
        }
      } catch (e) {
        console.warn('No config.json found, using defaults');
      }
    }
  }

  // Resolve a relative dataUrl against the config file's URL, so the CSV is
  // looked up next to the JSON rather than next to the app's index.html.
  if (config.dataUrl && loadedFromUrl) {
    config.dataUrl = new URL(config.dataUrl, loadedFromUrl).href;
  }

  // Resolve branding asset URLs against the config file's URL too. This lets
  // a site ship its own `ext/` folder next to zarrcade.json and reference
  // assets by relative path.
  if (loadedFromUrl && config.branding) {
    resolveBrandingAgainst(config.branding, loadedFromUrl);
  }

  // Check for data URL override in query params (resolved against the app URL)
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
