/**
 * Gallery grid component
 */

import type { ImageRow, AppConfig } from '../types';
import { ImageCard } from './ImageCard';

interface GalleryProps {
  data: ImageRow[];
  config: AppConfig;
}

export function Gallery({ data, config }: GalleryProps) {
  if (data.length === 0) {
    return (
      <div className="gallery-empty">
        <p>No images found.</p>
      </div>
    );
  }

  return (
    <div className="gallery">
      {data.map((row, index) => (
        <ImageCard key={index} row={row} config={config} />
      ))}
    </div>
  );
}
