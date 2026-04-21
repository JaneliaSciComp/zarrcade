/**
 * Search bar component
 */

import { useState, FormEvent } from 'react';

interface SearchBarProps {
  value: string;
  onChange: (value: string) => void;
  onReset: () => void;
}

export function SearchBar({ value, onChange, onReset }: SearchBarProps) {
  const [inputValue, setInputValue] = useState(value);

  const handleSubmit = (e: FormEvent) => {
    e.preventDefault();
    onChange(inputValue);
  };

  const handleReset = () => {
    setInputValue('');
    onReset();
  };

  return (
    <form className="search-bar" onSubmit={handleSubmit}>
      <input
        type="search"
        placeholder="Search..."
        value={inputValue}
        onChange={(e) => setInputValue(e.target.value)}
        aria-label="Search"
      />
      <button type="submit">Search</button>
      <button type="button" className="secondary" onClick={handleReset}>
        Reset
      </button>
    </form>
  );
}
