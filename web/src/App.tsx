/**
 * Main App component for Zarrcade SPA
 */

import { useState, useEffect } from 'react';
import type { AppConfig, ImageRow } from './types';
import { loadConfig } from './config';
import { useData } from './hooks/useData';
import { useSearch } from './hooks/useSearch';
import { useFilters } from './hooks/useFilters';
import { usePagination } from './hooks/usePagination';
import { useTheme } from './hooks/useTheme';
import { TopBar } from './components/TopBar';
import { SearchBar } from './components/SearchBar';
import { FilterDropdowns } from './components/FilterDropdowns';
import { Gallery } from './components/Gallery';
import { Pagination } from './components/Pagination';
import { ImageDetail } from './components/ImageDetail';
import { Footer } from './components/Footer';

function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [selectedImage, setSelectedImage] = useState<ImageRow | null>(null);
  const { theme, toggleTheme } = useTheme();

  // Load configuration
  useEffect(() => {
    loadConfig()
      .then(setConfig)
      .catch((e) => setConfigError(e.message));
  }, []);

  // Load data
  const { data, columns, loading, error: dataError } = useData(config);

  // Search
  const { searchTerm, setSearchTerm, searchResults } = useSearch(data);

  // Filters
  const filterConfigs = config?.filters || [];
  const {
    activeFilters,
    setFilter,
    clearFilters,
    filteredData,
    filterOptions,
  } = useFilters(searchResults, filterConfigs);

  // Pagination
  const pageSize = config?.display?.pageSize || 50;
  const {
    currentPage,
    totalPages,
    totalItems,
    paginatedData,
    goToPage,
    startIndex,
    endIndex,
  } = usePagination(filteredData, pageSize);

  // Handle reset (clear search and filters)
  const handleReset = () => {
    setSearchTerm('');
    clearFilters();
  };

  const handleImageClick = (row: ImageRow) => {
    setSelectedImage(row);
    window.scrollTo(0, 0);
  };

  const handleBack = () => {
    setSelectedImage(null);
  };

  // Error state
  if (configError) {
    return (
      <div className="error-container">
        <h2>Configuration Error</h2>
        <p>{configError}</p>
        <p>
          Please provide a <code>config.json</code> file or use the{' '}
          <code>?data=URL</code> parameter.
        </p>
      </div>
    );
  }

  // Loading state
  if (!config || loading) {
    return (
      <div className="loading-container">
        <p>Loading...</p>
      </div>
    );
  }

  // Data error state
  if (dataError) {
    return (
      <div className="error-container">
        <h2>Data Error</h2>
        <p>{dataError.message}</p>
      </div>
    );
  }

  return (
    <div className="app">
      <TopBar config={config} theme={theme} onToggleTheme={toggleTheme} />

      <main className="main-content">
        {selectedImage ? (
          <ImageDetail
            row={selectedImage}
            columns={columns}
            config={config}
            onBack={handleBack}
          />
        ) : (
          <>
            <div className="controls">
              <SearchBar
                value={searchTerm}
                onChange={setSearchTerm}
                onReset={handleReset}
              />
              <FilterDropdowns
                filters={filterConfigs}
                filterOptions={filterOptions}
                activeFilters={activeFilters}
                onFilterChange={setFilter}
              />
            </div>

            <Gallery
              data={paginatedData}
              config={config}
              onImageClick={handleImageClick}
            />

            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              totalItems={totalItems}
              startIndex={startIndex}
              endIndex={endIndex}
              onPageChange={goToPage}
            />
          </>
        )}
      </main>

      <Footer config={config} />
    </div>
  );
}

export default App;
