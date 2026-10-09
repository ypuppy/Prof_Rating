import { useEffect, useState, useCallback } from 'react';
import { fetchProfessors } from '../api/professors';
import ProfessorList from '../features/professors/ProfessorList';
import ProfessorDetail from '../features/professors/ProfessorDetail';
import AddProfessorForm from '../features/professors/AddProfessorForm';
import Button from '../components/Button';
import { useAuth } from '../features/auth/AuthContext';
import MyReviewsModal from '../features/me/MyReviewsModal';
import './HomePage.css';

// Debounce hook
function useDebounce(value, delay) {
  const [debouncedValue, setDebouncedValue] = useState(value);
  
  useEffect(() => {
    const handler = setTimeout(() => setDebouncedValue(value), delay);
    return () => clearTimeout(handler);
  }, [value, delay]);
  
  return debouncedValue;
}

export default function HomePage() {
  const [professors, setProfessors] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [loading, setLoading] = useState(true);
  const [showAddForm, setShowAddForm] = useState(false);
  const [showMyReviews, setShowMyReviews] = useState(false);
  // Bumped whenever reviews change, so the open professor's detail reloads
  const [dataVersion, setDataVersion] = useState(0);
  
  const debouncedQuery = useDebounce(searchQuery, 300);
  const { user, checking, requireLogin, logout } = useAuth();

  const loadProfessors = useCallback(async (query = '') => {
    setLoading(true);
    try {
      const data = await fetchProfessors({ query });
      setProfessors(data);
    } catch (err) {
      console.error('Failed to fetch professors:', err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfessors(debouncedQuery);
  }, [debouncedQuery, loadProfessors]);

  const handleReviewsChanged = () => {
    setDataVersion((v) => v + 1);
    loadProfessors(debouncedQuery);
  };

  const handleCloseDetail = () => {
    setSelectedId(null);
  };

  const handleProfessorAdded = (newProfessor) => {
    setShowAddForm(false);
    loadProfessors(debouncedQuery);
    setSelectedId(newProfessor.id);
  };

  return (
    <div className="app">
      {/* Header */}
      <header className="header">
        <div className="header-content">
          <a href="/" className="logo">
            <div className="logo-icon">📚</div>
            <span>ProfRating</span>
          </a>
          
          <div className="search-container">
            <div className="search-wrapper">
              <input
                type="text"
                className="search-input"
                placeholder="Search professors..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
              />
              <svg className="search-icon" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="11" cy="11" r="8"/>
                <path d="m21 21-4.35-4.35"/>
              </svg>
            </div>
          </div>

          <div className="header-actions">
            <Button 
              variant="primary" 
              size="sm"
              onClick={() => requireLogin(() => setShowAddForm(true))}
              icon="+"
            >
              Add Professor
            </Button>
            {!checking && (user ? (
              <div className="user-menu">
                <span className="user-email" title={user.email}>{user.email.split('@')[0]}</span>
                <Button variant="ghost" size="sm" onClick={() => setShowMyReviews(true)}>My Reviews</Button>
                <Button variant="ghost" size="sm" onClick={logout}>Log out</Button>
              </div>
            ) : (
              <Button variant="secondary" size="sm" onClick={() => requireLogin()}>
                Log in
              </Button>
            ))}
          </div>
        </div>
      </header>

      {/* Add Professor Modal */}
      {showAddForm && (
        <div className="modal-overlay" onClick={() => setShowAddForm(false)}>
          <div className="modal-content animate-scale-in" onClick={e => e.stopPropagation()}>
            <AddProfessorForm 
              onSuccess={handleProfessorAdded}
              onCancel={() => setShowAddForm(false)}
              onOpenExisting={(id) => {
                setShowAddForm(false);
                setSelectedId(id);
              }}
            />
          </div>
        </div>
      )}

      {/* My Reviews Modal (closes itself if the user logs out) */}
      {showMyReviews && user && (
        <div className="modal-overlay" onClick={() => setShowMyReviews(false)}>
          <div className="modal-content my-reviews-modal animate-scale-in" onClick={e => e.stopPropagation()}>
            <MyReviewsModal
              onClose={() => setShowMyReviews(false)}
              onSelectProfessor={(id) => {
                setSelectedId(id);
                setShowMyReviews(false);
              }}
              onChanged={handleReviewsChanged}
            />
          </div>
        </div>
      )}

      {/* Main Content */}
      <main className="main-content">
        <div className="content-grid">
          {/* Professor List */}
          <section className="professors-section">
            <div className="section-header">
              <h2 className="section-title">Professors</h2>
              <span className="section-count">{professors.length}</span>
            </div>
            <ProfessorList
              items={professors}
              selectedId={selectedId}
              onSelect={setSelectedId}
              loading={loading}
            />
          </section>

          {/* Professor Detail */}
          <section className="detail-section">
            <ProfessorDetail 
              professorId={selectedId}
              onClose={handleCloseDetail}
              refreshKey={dataVersion}
              onReviewsChanged={handleReviewsChanged}
            />
          </section>
        </div>
      </main>
    </div>
  );
}