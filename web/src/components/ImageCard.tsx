/**
 * Image card component for gallery
 */

import { useState } from 'react';
import type { ImageRow, AppConfig, Viewer } from '../types';
import { getImagePath, getThumbnailUrl, getTitle } from '../utils/csv';
import { getViewerUrl, getEnabledViewers } from '../utils/viewers';
import { copyToClipboard } from '../utils/clipboard';

interface ImageCardProps {
  row: ImageRow;
  config: AppConfig;
}

export function ImageCard({ row, config }: ImageCardProps) {
  const [showCopied, setShowCopied] = useState(false);

  const imagePath = getImagePath(row, config);
  const thumbnailUrl = getThumbnailUrl(row, config);
  const title = getTitle(row, config);
  const viewers = getEnabledViewers(config.viewers);

  const handleCopyLink = async () => {
    const success = await copyToClipboard(imagePath);
    if (success) {
      setShowCopied(true);
      setTimeout(() => setShowCopied(false), 1500);
    }
  };

  return (
    <div className="image-card">
      <div className="image-card-thumbnail">
        <img
          src={thumbnailUrl}
          alt={title}
          loading="lazy"
          onError={(e) => {
            (e.target as HTMLImageElement).src = './icons/zarr.jpg';
          }}
        />
        <div className="image-card-overlay">
          <div className="overlay-buttons">
            <button
              className="overlay-button"
              onClick={handleCopyLink}
              title="Copy data URL"
            >
              {showCopied ? '✓' : '📋'}
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
