import React, { useState, useEffect, useCallback } from 'react';
import { LiveStudentSearchRowView, LiveStudentSearchResponse, LiveStudentSearchParams } from '../types';
import { searchLiveStudents, checkStudentInArchive } from '../api';
import { useGelSession } from '../hooks/useGelSession';

interface LiveStudentSearchPaneProps {
  onSelect: (student: LiveStudentSearchRowView) => void;
}

export const LiveStudentSearchPane: React.FC<LiveStudentSearchPaneProps> = ({ onSelect }) => {
  const [searchTerm, setSearchTerm] = useState('');
  const [courseStartBefore, setCourseStartBefore] = useState<string | null>(null);
  const [courseEndAfter, setCourseEndAfter] = useState<string | null>(null);
  const [results, setResults] = useState<LiveStudentSearchRowView[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [response, setResponse] = useState<LiveStudentSearchResponse | null>(null);
  const { isAuthenticated } = useGelSession();

  const handleSearch = useCallback(() => {
    if (searchTerm.trim()) {
      setPage(1);
    }
  }, [searchTerm]);

  const handleKeyPress = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  useEffect(() => {
    const performSearch = async () => {
      if (!isAuthenticated || !searchTerm.trim()) {
        setResults([]);
        setResponse(null);
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        const params: LiveStudentSearchParams = {
          searchTerm: searchTerm.trim(),
          courseStartBefore: courseStartBefore || undefined,
          courseEndAfter: courseEndAfter || undefined,
          page,
          pageSize: 25,
        };

        const result = await searchLiveStudents(params);
        setResponse(result);
        setResults(result.rows);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to search students');
        setResults([]);
        setResponse(null);
      } finally {
        setIsLoading(false);
      }
    };

    performSearch();
  }, [searchTerm, courseStartBefore, courseEndAfter, page, isAuthenticated]);

  const handlePageChange = (newPage: number) => {
    setPage(newPage);
  };

  const totalPages = response ? Math.ceil(response.totalEntries / 25) : 0;

  const formatCaptureRate = (rate: number): string => {
    return `${(rate * 100).toFixed(1)}%`;
  };

  if (!isAuthenticated) {
    return (
      <div className="live-student-search-pane">
        <div className="search-placeholder">
          <p>Please log in to search for students.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="live-student-search-pane">
      <div className="search-header">
        <h2>School-Wide Student Search</h2>
        
        <div className="search-filters">
          <div className="filter-group">
            <label htmlFor="search-term">Search Term:</label>
            <input
              id="search-term"
              type="text"
              className="search-input"
              placeholder="Name, UID, or course..."
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
          </div>

          <div className="filter-group date-filters">
            <div className="date-filter">
              <label htmlFor="course-start-before">Course Start Before:</label>
              <input
                id="course-start-before"
                type="date"
                value={courseStartBefore || ''}
                onChange={(e) => setCourseStartBefore(e.target.value || null)}
                disabled={isLoading}
              />
            </div>
            <div className="date-filter">
              <label htmlFor="course-end-after">Course End After:</label>
              <input
                id="course-end-after"
                type="date"
                value={courseEndAfter || ''}
                onChange={(e) => setCourseEndAfter(e.target.value || null)}
                disabled={isLoading}
              />
            </div>
          </div>
        </div>

        {response && (
          <div className="governance-indicators">
            <span className="capture-rate-badge" title="Percentage of total entries returned">
              Capture Rate: {formatCaptureRate(response.captureRate)}
            </span>
            <span className="pages-fetched-info">
              Pages Fetched: {response.pagesFetched}
            </span>
            <span className="total-entries-info">
              Total Entries: {response.totalEntries}
            </span>
          </div>
        )}
      </div>

      <div className="search-results">
        {error && <div className="error-message">{error}</div>}

        {!searchTerm.trim() && !error && (
          <div className="search-placeholder">
            <p>Enter a search term to find students across the school.</p>
          </div>
        )}

        {searchTerm.trim() && results.length === 0 && !isLoading && !error && (
          <div className="no-results">
            <p>No students found matching "{searchTerm}".</p>
          </div>
        )}

        {results.length > 0 && response && (
          <>
            <div className="results-info">
              <span>
                Showing {results.length} of {response.totalEntries} results
              </span>
              {response.infoFooterRaw && (
                <span className="info-footer-raw" title="DataTables footer">
                  {response.infoFooterRaw}
                </span>
              )}
            </div>

            <table className="search-results-table">
              <thead>
                <tr>
                  <th>UID</th>
                  <th>Name</th>
                  <th>Course Start</th>
                  <th>Course End</th>
                  <th>Tutorial End</th>
                  <th>Tutor</th>
                  <th>Absent</th>
                  <th>Archive</th>
                </tr>
              </thead>
              <tbody>
                {results.map((student) => (
                  <tr
                    key={student.uid}
                    className="student-row"
                    onClick={() => onSelect(student)}
                    style={{ cursor: 'pointer' }}
                  >
                    <td className="uid-column">{student.uid}</td>
                    <td className="name-column">{student.fullName}</td>
                    <td>{student.courseStart || '—'}</td>
                    <td>{student.courseEnd || '—'}</td>
                    <td>{student.tutorialEnd || '—'}</td>
                    <td>{student.tutorName || '—'}</td>
                    <td>
                      {student.isAbsent ? (
                        <span className="absent-badge">Yes</span>
                      ) : (
                        <span className="present-badge">No</span>
                      )}
                    </td>
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

export default LiveStudentSearchPane;
