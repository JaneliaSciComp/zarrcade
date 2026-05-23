/**
 * Tabular view of the dataset's metadata.
 *
 * Shows all visible columns (respecting display.hideColumns); each cell
 * truncates with ellipsis and a title tooltip carrying the full text.
 * Clicking a row opens that image's detail page.
 */

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
            const globalIndex = allData.indexOf(row);
            const rowKey = row[pathColumn] !== undefined ? String(row[pathColumn]) : `row-${globalIndex}`;
            return (
              <tr key={rowKey} onClick={() => onRowClick(globalIndex)}>
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
