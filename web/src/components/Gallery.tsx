/**
 * Gallery grid component
 */

import { useMemo } from 'react';
import type { ImageRow, AppConfig } from '../types';
import { ImageCard } from './ImageCard';

interface GalleryProps {
  data: ImageRow[];
  allData: ImageRow[];
  config: AppConfig;
  onImageClick: (index: number) => void;
}

export function Gallery({ data, allData, config, onImageClick }: GalleryProps) {
  // Build a row→index map once per allData change. Looking the index up
  // via allData.indexOf() inside the .map() below was O(n) per card and
  // O(n²) per render, which got painful for larger collections.
  const indexByRow = useMemo(() => {
    const m = new Map<ImageRow, number>();
    allData.forEach((row, i) => m.set(row, i));
    return m;
  }, [allData]);

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
        const globalIndex = indexByRow.get(row) ?? -1;
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
