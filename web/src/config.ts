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
 * Try to load a local config file. Returns null when the file is absent
 * (404/network error) so callers can silently fall through to the next
 * source. A non-404 HTTP error or malformed JSON throws — those represent
 * real misconfiguration the user needs to see.
 */
async function tryLoadLocalConfig(
  path: string,
): Promise<{ config: Partial<AppConfig>; loadedFromUrl: string } | null> {
  let response: Response;
  try {
    response = await fetch(path);
  } catch {
    return null;
  }
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw new Error(
      `Failed to load ${path}: ${response.status} ${response.statusText}`.trim(),
    );
  }
  let parsed: Partial<AppConfig>;
  try {
    parsed = await response.json();
  } catch (e) {
    throw new Error(
      `${path} is not valid JSON: ${e instanceof Error ? e.message : String(e)}`,
    );
  }
  return {
    config: parsed,
    loadedFromUrl: new URL(path, window.location.href).href,
  };
}

/**
 * Load configuration from various sources.
 * Priority: `?config=` query param > /config.local.json (dev only) >
 *          /config.json > built-in defaults
 */
export async function loadConfig(): Promise<AppConfig | null> {
  const urlParams = new URLSearchParams(window.location.search);
  const configUrl = urlParams.get('config');

  let config: Partial<AppConfig> = {};
  // The absolute URL of the config file we actually loaded; used to resolve
  // a relative dataUrl against the config's location rather than the app URL.
  let loadedFromUrl: string | null = null;

  if (configUrl) {
    // Explicit ?config=<url>: surface every failure mode to the user. A typo
    // or 404 here is almost certainly the reason they're hitting the page,
    // so swallowing it and rendering the Welcome screen would be misleading.
    let response: Response;
    try {
      response = await fetch(configUrl);
    } catch (e) {
      throw new Error(
        `Failed to fetch config from ${configUrl}: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
    if (!response.ok) {
      throw new Error(
        `Failed to fetch config from ${configUrl}: ${response.status} ${response.statusText}`.trim(),
      );
    }
    try {
      config = await response.json();
    } catch (e) {
      throw new Error(
        `Config at ${configUrl} is not valid JSON: ${e instanceof Error ? e.message : String(e)}`,
      );
    }
    loadedFromUrl = new URL(configUrl, window.location.href).href;
  } else {
    // Local config files: a missing file is fine (fall through to defaults /
    // Welcome), but malformed JSON in a file the user shipped should surface.
    const local = await tryLoadLocalConfig('./config.local.json');
    if (local) {
      config = local.config;
      loadedFromUrl = local.loadedFromUrl;
    } else {
      const main = await tryLoadLocalConfig('./config.json');
      if (main) {
        config = main.config;
        loadedFromUrl = main.loadedFromUrl;
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
