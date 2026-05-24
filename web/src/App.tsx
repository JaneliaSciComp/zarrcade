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
import { copyToClipboard } from './utils/clipboard';
import { TopBar } from './components/TopBar';
import { SearchBar } from './components/SearchBar';
import { FilterDropdowns } from './components/FilterDropdowns';
import { Gallery } from './components/Gallery';
import { TableView } from './components/TableView';
import { ViewToggle, type ViewMode } from './components/ViewToggle';
import { Pagination } from './components/Pagination';
import { ImageDetail } from './components/ImageDetail';
import { Footer } from './components/Footer';
import { Welcome } from './components/Welcome';

function App() {
  const [config, setConfig] = useState<AppConfig | null>(null);
  const [configError, setConfigError] = useState<string | null>(null);
  const [configLoaded, setConfigLoaded] = useState(false);
  const [selectedImageIndex, setSelectedImageIndex] = useState<number | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>('gallery');
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

  // Sync the browser tab title with the configured title; fall back to
  // "Zarrcade" for error / Welcome / loading states.
  useEffect(() => {
    document.title = !configError && config?.title ? config.title : 'Zarrcade';
  }, [config?.title, configError]);

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

  // Initialize detail view and view mode from URL; re-read on popstate.
  useEffect(() => {
    const readFromUrl = () => {
      const params = new URLSearchParams(window.location.search);
      const detailParam = params.get('detail');
      if (detailParam !== null) {
        const index = parseInt(detailParam, 10);
        setSelectedImageIndex(!isNaN(index) ? index : null);
      } else {
        setSelectedImageIndex(null);
      }

      const viewParam = params.get('view');
      setViewMode(viewParam === 'table' ? 'table' : 'gallery');
    };

    readFromUrl();
    window.addEventListener('popstate', readFromUrl);
    return () => window.removeEventListener('popstate', readFromUrl);
  }, []);

  const handleViewModeChange = useCallback((mode: ViewMode) => {
    setViewMode(mode);
    const params = new URLSearchParams(window.location.search);
    if (mode === 'gallery') {
      params.delete('view');
    } else {
      params.set('view', mode);
    }
    const qs = params.toString();
    const newUrl = `${window.location.pathname}${qs ? '?' + qs : ''}`;
    window.history.pushState({}, '', newUrl);
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

  const pageActions = [
    {
      label: 'Copy link to current view',
      icon: 'fa-solid fa-link',
      onClick: () => copyToClipboard(window.location.href),
    },
    ...(selectedImage
      ? []
      : [
          {
            label: 'Download metadata as CSV',
            icon: 'fa-solid fa-download',
            onClick: () => downloadCsv(data, columns, config, 'metadata.csv'),
          },
          {
            label: 'View collection in BioFile Finder',
            icon: 'fa-solid fa-table-cells',
            href: getBioFileFinderUrl(config),
          },
        ]),
  ];

  const siteItems = (config.branding?.menuItems || []).map((item) => ({
    label: item.label,
    icon: item.icon || 'fa-solid fa-link',
    href: item.href,
  }));

  return (
    <div className="app">
      <TopBar
        config={config}
        theme={theme}
        onToggleTheme={toggleTheme}
        menuGroups={[pageActions, siteItems]}
      />

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

            <div className="pagination-row">
              <ViewToggle value={viewMode} onChange={handleViewModeChange} />
              <Pagination
                currentPage={currentPage}
                totalPages={totalPages}
                totalItems={totalItems}
                startIndex={startIndex}
                endIndex={endIndex}
                onPageChange={goToPage}
              />
            </div>

            {viewMode === 'table' ? (
              <TableView
                data={paginatedData}
                allData={data}
                columns={columns}
                config={config}
                onRowClick={handleImageClick}
              />
            ) : (
              <>
                <hr className="gallery-rule" />
                <Gallery
                  data={paginatedData}
                  allData={data}
                  config={config}
                  onImageClick={handleImageClick}
                />
                <hr className="gallery-rule" />
              </>
            )}

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
