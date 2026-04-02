/**
 * Image detail page component
 */

import { useState } from 'react';
import type { ImageRow, AppConfig } from '../types';
import { getImagePath, getThumbnailUrl, getTitle, getVisibleColumns } from '../utils/csv';
import { getViewerUrl, getEnabledViewers } from '../utils/viewers';
import { copyToClipboard } from '../utils/clipboard';

interface ImageDetailProps {
  row: ImageRow;
  columns: string[];
  config: AppConfig;
  onBack: () => void;
}

export function ImageDetail({ row, columns, config, onBack }: ImageDetailProps) {
  const [showCopied, setShowCopied] = useState(false);

  const imagePath = getImagePath(row, config);
  const thumbnailUrl = getThumbnailUrl(row, config);
  const title = getTitle(row, config);
  const viewers = getEnabledViewers(config.viewers);
  const visibleColumns = getVisibleColumns(columns, config);

  const handleCopyLink = async () => {
    const success = await copyToClipboard(imagePath);
    if (success) {
      setShowCopied(true);
      setTimeout(() => setShowCopied(false), 1500);
    }
  };

  return (
    <div className="image-detail">
      <nav className="image-detail-nav">
        <button className="image-detail-back" onClick={onBack}>
          &larr; Back to gallery
        </button>
      </nav>

      <div className="image-detail-header">
        <h2 dangerouslySetInnerHTML={{ __html: title }} />
        <div className="image-detail-actions">
          <button className="outline" onClick={handleCopyLink} title="Copy data URL">
            <i className={showCopied ? 'fa-regular fa-circle-check' : 'fa-regular fa-clipboard'} />
            {showCopied ? ' Copied!' : ' Copy data link'}
          </button>
          {viewers.map((viewer) => (
            <a
              key={viewer.name}
              href={getViewerUrl(viewer, imagePath)}
              target="_blank"
              rel="noopener noreferrer"
              className="outline"
              role="button"
              title={`Open in ${viewer.name}`}
            >
              <img
                src={`./icons/${viewer.icon}`}
                alt={viewer.name}
                className="image-detail-viewer-icon"
              />
              {viewer.name}
            </a>
          ))}
        </div>
      </div>

      <div className="image-detail-body">
        <div className="image-detail-thumbnail">
          <img
            src={thumbnailUrl}
            alt={title}
            onError={(e) => {
              (e.target as HTMLImageElement).src = './icons/zarr.jpg';
            }}
          />
        </div>

        <table className="image-detail-metadata">
          <tbody>
            {visibleColumns.map((col) => {
              const value = row[col];
              if (value === undefined || value === '') return null;
              return (
                <tr key={col}>
                  <th>{col}</th>
                  <td>{String(value)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}
