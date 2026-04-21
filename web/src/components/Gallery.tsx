/**
 * Gallery grid component
 */

import type { ImageRow, AppConfig } from '../types';
import { ImageCard } from './ImageCard';

interface GalleryProps {
  data: ImageRow[];
  allData: ImageRow[];
  config: AppConfig;
  onImageClick: (index: number) => void;
}

export function Gallery({ data, allData, config, onImageClick }: GalleryProps) {
  if (data.length === 0) {
    return (
      <div className="gallery-empty">
        <p>No images found.</p>
      </div>
    );
  }

  const pathColumn = config.data?.pathColumn || 'path';
  return (
    <div className="gallery">
      {data.map((row) => {
        const globalIndex = allData.indexOf(row);
        const rowKey = row[pathColumn] !== undefined ? String(row[pathColumn]) : `row-${globalIndex}`;
        return (
          <ImageCard
            key={rowKey}
            row={row}
            config={config}
            onClick={() => onImageClick(globalIndex)}
          />
        );
      })}
    </div>
  );
}
