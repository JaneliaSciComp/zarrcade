/**
 * Image card component for gallery
 */

import { useEffect, useState } from 'react';
import type { ImageRow, AppConfig, Viewer } from '../types';
import {
  getCsvThumbnailUrl,
  getImagePath,
  getPlainTitle,
  getTitle,
  THUMBNAIL_PLACEHOLDER,
} from '../utils/csv';
import { getViewerUrl, getEnabledViewers } from '../utils/viewers';
import { copyToClipboard } from '../utils/clipboard';
import { useIntersectionObserver } from '../hooks/useIntersectionObserver';
import { useZarrThumbnail } from '../hooks/useZarrThumbnail';

interface ImageCardProps {
  row: ImageRow;
  config: AppConfig;
  onClick: () => void;
}

const THUMBNAIL_TARGET_SIZE = 300;

export function ImageCard({ row, config, onClick }: ImageCardProps) {
  const [showCopied, setShowCopied] = useState(false);

  const imagePath = getImagePath(row, config);
  const csvThumbnail = getCsvThumbnailUrl(row, config);
  const title = getTitle(row, config);
  const plainTitle = getPlainTitle(row, config);
  const viewers = getEnabledViewers(config.viewers);

  const { ref, inView } = useIntersectionObserver<HTMLDivElement>({
    rootMargin: '200px',
  });

  const conventionThumbnail = useZarrThumbnail(
    csvThumbnail ? null : imagePath,
    THUMBNAIL_TARGET_SIZE,
    inView
  );

  // Thumbnail resolution is a tri-state:
  //   'loading'   — we haven't determined yet (waiting on viewport, zarr.json
  //                 fetch, or the image to decode)
  //   'image'     — we have a thumbnail URL, decoded and ready to render
  //   'empty'     — we've confirmed there is no thumbnail; render the zarr
  //                 fallback icon
  type ThumbState =
    | { kind: 'loading' }
    | { kind: 'image'; url: string }
    | { kind: 'empty' };
  const [thumbState, setThumbState] = useState<ThumbState>({ kind: 'loading' });

  // resolvedUrl: undefined = still resolving, null = nothing to load, string = URL
  let resolvedUrl: string | null | undefined;
  if (csvThumbnail) {
    resolvedUrl = csvThumbnail;
  } else if (conventionThumbnail === undefined) {
    resolvedUrl = undefined;
  } else if (conventionThumbnail === null) {
    resolvedUrl = null;
  } else {
    resolvedUrl = conventionThumbnail.url;
  }

  useEffect(() => {
    if (resolvedUrl === undefined) {
      setThumbState({ kind: 'loading' });
      return;
    }
    if (resolvedUrl === null) {
      setThumbState({ kind: 'empty' });
      return;
    }
    // We have a URL; preload it so we don't flash a partially-decoded image
    // and don't keep stale pixels from the previous page on slow connections.
    setThumbState({ kind: 'loading' });
    const img = new Image();
    let cancelled = false;
    img.onload = () => { if (!cancelled) setThumbState({ kind: 'image', url: resolvedUrl }); };
    img.onerror = () => { if (!cancelled) setThumbState({ kind: 'empty' }); };
    img.src = resolvedUrl;
    return () => {
      cancelled = true;
      img.onload = null;
      img.onerror = null;
    };
  }, [resolvedUrl]);

  const handleCopyLink = async () => {
    const success = await copyToClipboard(imagePath);
    if (success) {
      setShowCopied(true);
      setTimeout(() => setShowCopied(false), 1500);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLDivElement>) => {
    if (e.key === 'Enter' || e.key === ' ') {
      e.preventDefault();
      onClick();
    }
  };

  return (
    <div
      ref={ref}
      className="image-card"
      role="button"
      tabIndex={0}
      aria-label={`Open ${plainTitle}`}
      onClick={onClick}
      onKeyDown={handleKeyDown}
    >
      <div className="image-card-thumbnail">
        {thumbState.kind === 'loading' ? (
          <div
            className="image-card-skeleton"
            role="img"
            aria-label="Loading thumbnail"
          />
        ) : (
          <img
            src={thumbState.kind === 'image' ? thumbState.url : THUMBNAIL_PLACEHOLDER}
            alt={plainTitle}
            loading="lazy"
            onError={(e) => {
              (e.target as HTMLImageElement).src = THUMBNAIL_PLACEHOLDER;
            }}
          />
        )}
        <div className="image-card-overlay">
          <div className="overlay-buttons" onClick={(e) => e.stopPropagation()}>
            <button
              className="overlay-button"
              onClick={handleCopyLink}
              title="Copy data URL"
              aria-label="Copy data URL"
            >
              <i className={showCopied ? 'fa-regular fa-circle-check' : 'fa-regular fa-clipboard'} />
            </button>
            {viewers.map((viewer) => (
              <ViewerButton key={viewer.name} viewer={viewer} dataUrl={imagePath} />
            ))}
          </div>
        </div>
      </div>
      <div
        className="image-card-title"
        dangerouslySetInnerHTML={{ __html: title }}
      />
    </div>
  );
}

interface ViewerButtonProps {
  viewer: Viewer;
  dataUrl: string;
}

function ViewerButton({ viewer, dataUrl }: ViewerButtonProps) {
  const viewerUrl = getViewerUrl(viewer, dataUrl);

  return (
    <a
      href={viewerUrl}
      target="_blank"
      rel="noopener noreferrer"
      className="overlay-button viewer-button"
      title={`Open in ${viewer.name}`}
    >
      <img
        src={`./icons/${viewer.icon}`}
        alt={viewer.name}
        onError={(e) => {
          (e.target as HTMLImageElement).style.display = 'none';
        }}
      />
    </a>
  );
}
