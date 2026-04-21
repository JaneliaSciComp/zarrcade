/**
 * Shown when the SPA loads without any data/config configured.
 * Explains how to point it at a dataset.
 */

export function Welcome() {
  const base = `${window.location.origin}${window.location.pathname}`;

  return (
    <div className="welcome">
      <h1>Zarrcade</h1>
      <p className="welcome-tagline">
        Browse, search, and visualize collections of OME-NGFF (OME-Zarr) images.
      </p>

      <section>
        <h2>Getting started</h2>
        <p>
          Zarrcade reads a CSV (or TSV) file describing your images. Point it at
          your data with one of these methods:
        </p>

        <h3>1. Pass a data URL</h3>
        <p>
          The simplest way — append <code>?data=</code> to the URL with a link to your CSV:
        </p>
        <pre><code>{base}?data=https://example.com/images.csv</code></pre>

        <h3>2. Pass a config URL</h3>
        <p>
          For more control (custom columns, filters, viewers, branding), supply
          a JSON configuration file:
        </p>
        <pre><code>{base}?config=https://example.com/config.json</code></pre>

        <h3>3. Bundle a config.json</h3>
        <p>
          If you're self-hosting, drop a <code>config.json</code> next to the
          SPA's <code>index.html</code>. It will be loaded automatically.
        </p>
      </section>

      <section>
        <h2>Need more?</h2>
        <p>
          See the{' '}
          <a
            href="https://github.com/JaneliaSciComp/zarrcade"
            target="_blank"
            rel="noopener noreferrer"
          >
            project documentation
          </a>{' '}
          for the full configuration reference and CLI tools for generating
          data and thumbnails.
        </p>
      </section>
    </div>
  );
}
