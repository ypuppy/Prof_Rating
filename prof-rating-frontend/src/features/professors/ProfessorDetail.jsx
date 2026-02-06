import { useEffect, useState } from 'react';
import { fetchProfessorDetail } from '../../api/professors';
import { fetchReviews } from '../../api/reviews';
import Card from '../../components/Card';
import Stars from '../../components/stars';
import Pill from '../../components/Pill';
import Button from '../../components/Button';
import ReviewForm from '../reviews/ReviewForm';
import ReviewList from '../reviews/Reviewlist';
import './ProfessorDetail.css';

export default function ProfessorDetail({ professorId, onClose }) {
  const [professor, setProfessor] = useState(null);
  const [reviews, setReviews] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showReviewForm, setShowReviewForm] = useState(false);

  const loadData = async () => {
    if (!professorId) return;
    
    setLoading(true);
    try {
      const [profData, reviewsData] = await Promise.all([
        fetchProfessorDetail(professorId),
        fetchReviews(professorId)
      ]);
      setProfessor(profData);
      setReviews(reviewsData);
    } catch (err) {
      console.error('Failed to load professor details:', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [professorId]);

  const handleReviewSubmitted = () => {
    setShowReviewForm(false);
    loadData(); // Refresh data
  };

  if (!professorId) {
    return (
      <Card className="professor-detail-empty" variant="flat">
        <div className="empty-illustration">
          <span>📚</span>
        </div>
        <h3>Select a Professor</h3>
        <p>Choose a professor from the list to view their details and reviews</p>
      </Card>
    );
  }

  if (loading) {
    return (
      <div className="professor-detail-loading">
        <div className="skeleton" style={{ height: 160, borderRadius: 24 }} />
        <div className="skeleton" style={{ height: 80, borderRadius: 16, marginTop: 16 }} />
        <div className="skeleton" style={{ height: 80, borderRadius: 16, marginTop: 12 }} />
      </div>
    );
  }

  if (!professor) {
    return (
      <Card className="professor-detail-empty" variant="flat">
        <p>Professor not found</p>
      </Card>
    );
  }

  return (
    <div className="professor-detail animate-scale-in">
      {/* Header Card */}
      <Card className="professor-detail-header" variant="elevated">
        <button className="close-btn" onClick={onClose} aria-label="Close">
          ✕
        </button>
        
        <div className="detail-avatar">
          {professor.name?.charAt(0) || '?'}
        </div>
        
        <h1 className="detail-name">{professor.name}</h1>
        
        <div className="detail-meta">
          {professor.department && (
            <Pill variant="accent">{professor.department}</Pill>
          )}
          {professor.faculty && (
            <Pill variant="default">{professor.faculty}</Pill>
          )}
        </div>

        <div className="detail-rating">
          {professor.avg_rating ? (
            <>
              <div className="rating-big">
                <span className="rating-number">{professor.avg_rating.toFixed(1)}</span>
                <span className="rating-max">/ 5</span>
              </div>
              <Stars value={professor.avg_rating} size="lg" />
              <p className="rating-count">
                Based on {professor.review_count} {professor.review_count === 1 ? 'review' : 'reviews'}
              </p>
            </>
          ) : (
            <p className="no-rating">No ratings yet</p>
          )}
        </div>

        <Button 
          variant="primary" 
          fullWidth
          onClick={() => setShowReviewForm(true)}
          icon="✍️"
        >
          Write a Review
        </Button>
      </Card>

      {/* Review Form Modal */}
      {showReviewForm && (
        <div className="review-form-overlay" onClick={() => setShowReviewForm(false)}>
          <div className="review-form-modal animate-slide-up" onClick={e => e.stopPropagation()}>
            <ReviewForm 
              professorId={professorId}
              professorName={professor.name}
              onSubmitted={handleReviewSubmitted}
              onCancel={() => setShowReviewForm(false)}
            />
          </div>
        </div>
      )}

      {/* Reviews Section */}
      <div className="reviews-section">
        <div className="section-header">
          <h2 className="section-title">Reviews</h2>
          <span className="section-count">{reviews.length}</span>
        </div>
        
        <ReviewList reviews={reviews} />
      </div>
    </div>
  );
}