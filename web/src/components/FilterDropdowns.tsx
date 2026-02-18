/**
 * Filter dropdowns component
 */

import type { FilterConfig, FilterState } from '../types';

interface FilterDropdownsProps {
  filters: FilterConfig[];
  filterOptions: Record<string, string[]>;
  activeFilters: FilterState;
  onFilterChange: (column: string, value: string) => void;
}

export function FilterDropdowns({
  filters,
  filterOptions,
  activeFilters,
  onFilterChange,
}: FilterDropdownsProps) {
  if (filters.length === 0) {
    return null;
  }

  return (
    <div className="filter-dropdowns">
      {filters.map((filter) => (
        <div key={filter.column} className="filter-dropdown">
          <select
            value={activeFilters[filter.column] || ''}
            onChange={(e) => onFilterChange(filter.column, e.target.value)}
            aria-label={filter.label}
          >
            <option value="">{filter.label}</option>
            {filterOptions[filter.column]?.map((option) => (
              <option key={option} value={option}>
                {option}
              </option>
            ))}
          </select>
        </div>
      ))}
    </div>
  );
}
