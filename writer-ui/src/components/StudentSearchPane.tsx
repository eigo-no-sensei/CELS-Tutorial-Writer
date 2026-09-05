import React, { useState, useEffect, useCallback } from 'react';
import { StudentSearchResult, StudentSearchParams } from '../types';
import { searchLiveStudents } from '../api';
import { useGelSession } from '../hooks/useGelSession';

interface StudentSearchPaneProps {
  onStudentSelect: (student: StudentSearchResult) => void;
  onStudentDeselect: (uid: number) => void;
  selectedStudents: Set<number>;
}

export const StudentSearchPane: React.FC<StudentSearchPaneProps> = ({
  onStudentSelect,
  onStudentDeselect,
  selectedStudents,
}) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [debouncedSearchTerm, setDebouncedSearchTerm] = useState('');
  const [results, setResults] = useState<StudentSearchResult[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalRecords, setTotalRecords] = useState(0);
  const { isAuthenticated } = useGelSession();

  // Handle explicit search trigger
  const handleSearch = useCallback(() => {
    if (searchTerm.trim()) {
      setDebouncedSearchTerm(searchTerm.trim());
      setPage(1); // Reset to first page on new search
    }
  }, [searchTerm]);

  // Handle Enter key press
  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  // Perform search when debounced term or page changes
  useEffect(() => {
    const performSearch = async () => {
      if (!isAuthenticated || !debouncedSearchTerm.trim()) {
        setResults([]);
        setTotalRecords(0);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const response = await searchLiveStudents(debouncedSearchTerm.trim(), page, 25);
        setResults(response.results);
        setTotalRecords(response.totalRecords);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to search students');
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    };

    performSearch();
  }, [debouncedSearchTerm, page, isAuthenticated]);

  const handleToggleStudent = useCallback(
    (student: StudentSearchResult) => {
      if (selectedStudents.has(student.uid)) {
        onStudentDeselect(student.uid);
      } else {
        onStudentSelect(student);
      }
    },
    [selectedStudents, onStudentSelect, onStudentDeselect]
  );

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  const totalPages = Math.ceil(totalRecords / 25);

  if (!isAuthenticated) {
    return (
      <div className="student-search-pane">
        <div className="search-placeholder">
          <p>Please log in to search for students.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="student-search-pane">
      <div className="search-header">
        <h2>Find Students</h2>
        <div className="search-input-container">
          <input
            type="text"
            className="search-input"
            placeholder="Search by name, UID, or course..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            onKeyPress={handleKeyPress}
            disabled={isLoading}
          />
          <button
            className="search-button"
            onClick={handleSearch}
            disabled={isLoading || !searchTerm.trim()}
            aria-label="Search students"
          >
            {isLoading ? 'Searching...' : 'Search'}
          </button>
          {isLoading && <span className="loading-indicator">Searching...</span>}
        </div>
      </div>

      <div className="search-results">
        {error && <div className="error-message">{error}</div>}

        {!debouncedSearchTerm.trim() && !error && (
          <div className="search-placeholder">
            <p>Enter a search term to find students across the school.</p>
          </div>
        )}

        {debouncedSearchTerm.trim() && results.length === 0 && !isLoading && !error && (
          <div className="no-results">
            <p>No students found matching "{debouncedSearchTerm}".</p>
          </div>
        )}

        {results.length > 0 && (
          <>
            <div className="results-info">
              <span>
                Showing {results.length} of {totalRecords} results
              </span>
            </div>

            <table className="search-results-table">
              <thead>
                <tr>
                  <th className="select-column">Select</th>
                  <th>UID</th>
                  <th>Name</th>
                  <th>Course Start</th>
                  <th>Course End</th>
                  <th>Tutorial End</th>
                  <th>Archive</th>
                </tr>
              </thead>
              <tbody>
                {results.map((student) => (
                  <tr
                    key={student.uid}
                    className={selectedStudents.has(student.uid) ? 'selected' : ''}
                  >
                    <td className="select-column">
                      <input
                        type="checkbox"
                        checked={selectedStudents.has(student.uid)}
                        onChange={() => handleToggleStudent(student)}
                        aria-label={`Select ${student.name}`}
                      />
                    </td>
                    <td className="uid-column">{student.uid}</td>
                    <td className="name-column">{student.name}</td>
                    <td>{student.courseStart || '—'}</td>
                    <td>{student.courseEnd || '—'}</td>
                    <td>{student.tutorialEnd || '—'}</td>
                    <td>
                      {student.inArchive ? (
                        <span className="archive-badge in-archive">In Archive</span>
                      ) : (
                        <span className="archive-badge not-in-archive">Not in Archive</span>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>

            {totalPages > 1 && (
              <div className="pagination">
                <button
                  onClick={() => handlePageChange(page - 1)}
                  disabled={page === 1}
                  className="pagination-btn"
                >
                  Previous
                </button>
                <span className="page-info">
                  Page {page} of {totalPages}
                </span>
                <button
                  onClick={() => handlePageChange(page + 1)}
                  disabled={page === totalPages}
                  className="pagination-btn"
                >
                  Next
                </button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default StudentSearchPane;
