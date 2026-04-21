/**
 * Main App component for Zarrcade SPA
 */

import { useState, useEffect, useCallback } from 'react';
import type { AppConfig } from './types';
import { loadConfig } from './config';
import { useData } from './hooks/useData';
import { useSearch } from './hooks/useSearch';
import { useFilters } from './hooks/useFilters';
import { usePagination } from './hooks/usePagination';
import { useTheme } from './hooks/useTheme';
import { downloadCsv, getBioFileFinderUrl } from './utils/csv';
import { TopBar } from './components/TopBar';
import { SearchBar } from './components/SearchBar';
import { FilterDropdowns } from './components/FilterDropdowns';
import { Gallery } from './components/Gallery';
import { Pagination } from './components/Pagination';
import { ImageDetail } from './components/ImageDetail';
import { Footer } from './components/Footer';
import { Welcome } from './components/Welcome';

function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [configLoaded, setConfigLoaded] = useState(false);
  const [selectedImageIndex, setSelectedImageIndex] = useState<number | null>(null);
  const { theme, toggleTheme } = useTheme();

  // Load configuration
  useEffect(() => {
    loadConfig()
      .then((c) => {
        setConfig(c);
        setConfigLoaded(true);
      })
      .catch((e) => {
        setConfigError(e.message);
        setConfigLoaded(true);
      });
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

  // Initialize detail view from URL and handle popstate (back button)
  useEffect(() => {
    const readDetailFromUrl = () => {
      const params = new URLSearchParams(window.location.search);
      const detailParam = params.get('detail');
      if (detailParam !== null) {
        const index = parseInt(detailParam, 10);
        if (!isNaN(index)) {
          setSelectedImageIndex(index);
          return;
        }
      }
      setSelectedImageIndex(null);
    };

    readDetailFromUrl();
    window.addEventListener('popstate', readDetailFromUrl);
    return () => window.removeEventListener('popstate', readDetailFromUrl);
  }, []);

  // Handle reset (clear search and filters)
  const handleReset = () => {
    setSearchTerm('');
    clearFilters();
  };

  const handleImageClick = useCallback((index: number) => {
    setSelectedImageIndex(index);
    const params = new URLSearchParams(window.location.search);
    params.set('detail', String(index));
    const newUrl = `${window.location.pathname}?${params.toString()}`;
    window.history.pushState({}, '', newUrl);
    window.scrollTo(0, 0);
  }, []);

  const handleBack = useCallback(() => {
    setSelectedImageIndex(null);
    const params = new URLSearchParams(window.location.search);
    params.delete('detail');
    const newUrl = `${window.location.pathname}${params.toString() ? '?' + params.toString() : ''}`;
    window.history.pushState({}, '', newUrl);
  }, []);

  const selectedImage = selectedImageIndex !== null ? data[selectedImageIndex] ?? null : null;

  // Config load failed (malformed JSON, network error, etc.)
  if (configError) {
    return (
      <div className="error-container">
        <h2>Configuration Error</h2>
        <p>{configError}</p>
      </div>
    );
  }

  // Still loading config
  if (!configLoaded) {
    return (
      <div className="loading-container">
        <p>Loading...</p>
      </div>
    );
  }

  // Config loaded but no dataUrl set — show setup instructions
  if (!config) {
    return (
      <div className="app">
        <TopBar config={null} theme={theme} onToggleTheme={toggleTheme} />
        <main className="main-content">
          <Welcome />
        </main>
        <Footer config={null} />
      </div>
    );
  }

  // Data still loading
  if (loading) {
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

            <div className="gallery-actions">
              <button
                className="gallery-action-link"
                onClick={() => downloadCsv(filteredData, columns, config, 'metadata.csv')}
              >
                <i className="fa-solid fa-download" /> Download metadata as CSV
              </button>
              <a
                className="gallery-action-link"
                href={getBioFileFinderUrl(config)}
                target="_blank"
                rel="noopener noreferrer"
              >
                <i className="fa-solid fa-table-cells" /> View collection in BioFile Finder
              </a>
            </div>

            <Pagination
              currentPage={currentPage}
              totalPages={totalPages}
              totalItems={totalItems}
              startIndex={startIndex}
              endIndex={endIndex}
              onPageChange={goToPage}
            />

            <Gallery
              data={paginatedData}
              allData={data}
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
