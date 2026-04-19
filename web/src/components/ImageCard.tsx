/**
 * Image card component for gallery
 */

import { useEffect, useState } from 'react';
import type { ImageRow, AppConfig, Viewer } from '../types';
import {
  getCsvThumbnailUrl,
  getImagePath,
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
  const viewers = getEnabledViewers(config.viewers);

  const { ref, inView } = useIntersectionObserver<HTMLDivElement>({
    rootMargin: '200px',
  });

  const conventionThumbnail = useZarrThumbnail(
    csvThumbnail ? null : imagePath,
    THUMBNAIL_TARGET_SIZE,
    inView
  );

  const resolvedUrl = csvThumbnail ?? conventionThumbnail?.url ?? null;

  // Preload the resolved thumbnail. Only display it once it has decoded;
  // until then, show the placeholder. This prevents stale images from the
  // previous page sticking around on slow connections.
  const [displayUrl, setDisplayUrl] = useState<string>(THUMBNAIL_PLACEHOLDER);
  useEffect(() => {
    setDisplayUrl(THUMBNAIL_PLACEHOLDER);
    if (!resolvedUrl) return;
    const img = new Image();
    let cancelled = false;
    img.onload = () => { if (!cancelled) setDisplayUrl(resolvedUrl); };
    img.onerror = () => { if (!cancelled) setDisplayUrl(THUMBNAIL_PLACEHOLDER); };
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

  return (
    <div
      ref={ref}
      className="image-card"
      onClick={onClick}
      style={{ cursor: 'pointer' }}
    >
      <div className="image-card-thumbnail">
        <img
          src={displayUrl}
          alt={title}
          loading="lazy"
          onError={(e) => {
            (e.target as HTMLImageElement).src = THUMBNAIL_PLACEHOLDER;
          }}
        />
        <div className="image-card-overlay">
          <div className="overlay-buttons" onClick={(e) => e.stopPropagation()}>
            <button
              className="overlay-button"
              onClick={handleCopyLink}
              title="Copy data URL"
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
