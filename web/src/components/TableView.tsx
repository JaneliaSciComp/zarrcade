/**
 * Tabular view of the dataset's metadata.
 *
 * Shows all visible columns (respecting display.hideColumns); each cell
 * truncates with ellipsis and a title tooltip carrying the full text.
 * Clicking a row opens that image's detail page.
 */

import { useMemo } from 'react';
import type { ImageRow, AppConfig } from '../types';
import { getVisibleColumns } from '../utils/csv';

interface TableViewProps {
  data: ImageRow[];
  allData: ImageRow[];
  columns: string[];
  config: AppConfig;
  onRowClick: (index: number) => void;
}

export function TableView({ data, allData, columns, config, onRowClick }: TableViewProps) {
  // Row→index map; avoids O(n) allData.indexOf() per row inside the render.
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

  const visibleColumns = getVisibleColumns(columns, config);
  const pathColumn = config.data?.pathColumn || 'path';

  return (
    <div className="table-view">
      <table>
        <thead>
          <tr>
            {visibleColumns.map((col) => (
              <th key={col}>{col}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row) => {
            const globalIndex = indexByRow.get(row) ?? -1;
            const rowKey = row[pathColumn] !== undefined ? String(row[pathColumn]) : `row-${globalIndex}`;
            const handleRowKeyDown = (e: React.KeyboardEvent<HTMLTableRowElement>) => {
              if (e.key === 'Enter' || e.key === ' ') {
                e.preventDefault();
                onRowClick(globalIndex);
              }
            };
            return (
              <tr
                key={rowKey}
                role="button"
                tabIndex={0}
                onClick={() => onRowClick(globalIndex)}
                onKeyDown={handleRowKeyDown}
              >
                {visibleColumns.map((col) => {
                  const raw = row[col];
                  const text = raw === undefined || raw === null ? '' : String(raw);
                  return (
                    <td key={col}>
                      <div className="table-cell-truncate" title={text}>
                        {text}
                      </div>
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
