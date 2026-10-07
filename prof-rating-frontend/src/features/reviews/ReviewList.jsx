import Card from '../../components/Card';
import Stars from '../../components/stars';
import Pill from '../../components/Pill';
import './ReviewList.css';

function formatDate(dateString) {
  if (!dateString) return '';
  const date = new Date(dateString);
  const now = new Date();
  const diffMs = now - date;
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  
  if (diffDays === 0) return 'Today';
  if (diffDays === 1) return 'Yesterday';
  if (diffDays < 7) return `${diffDays} days ago`;
  if (diffDays < 30) return `${Math.floor(diffDays / 7)} weeks ago`;
  if (diffDays < 365) return `${Math.floor(diffDays / 30)} months ago`;
  return `${Math.floor(diffDays / 365)} years ago`;
}

export default function ReviewList({ reviews = [] }) {
  if (reviews.length === 0) {
    return (
      <div className="reviews-empty">
        <div className="empty-icon">💬</div>
        <p>No reviews yet</p>
        <span>Be the first to share your experience!</span>
      </div>
    );
  }

  return (
    <div className="reviews-list stagger-children">
      {reviews.map((review) => (
        <Card key={review.id} className="review-card">
          <div className="review-header">
            <Stars value={review.rating} size="sm" />
            {review.module_code && (
              <Pill variant="accent" size="sm">{review.module_code}</Pill>
            )}
            <span className="review-date">{formatDate(review.created_at)}</span>
          </div>
          
          {review.comment ? (
            <p className="review-comment">{review.comment}</p>
          ) : (
            <p className="review-no-comment">No written review</p>
          )}
        </Card>
      ))}
    </div>
  );
}