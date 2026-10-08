import { useEffect, useState } from 'react';
import { deleteMyReview, discardDeletedReview, fetchDeletedReviews, fetchMyReviews } from '../../api/me';
import Button from '../../components/Button';
import Pill from '../../components/Pill';
import Stars from '../../components/stars';
import ReviewForm from '../reviews/ReviewForm';
import './MyReviewsModal.css';

function formatDate(iso) {
  return new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short', year: 'numeric' });
}

function hoursLeft(iso) {
  return Math.max(1, Math.ceil((new Date(iso) - Date.now()) / 3_600_000));
}

/** Groups reviews by professor, keeping the order of each professor's most recent review. */
function groupByProfessor(reviews) {
  const groups = new Map();
  for (const review of reviews) {
    const key = review.professor.id;
    if (!groups.has(key)) groups.set(key, { professor: review.professor, reviews: [] });
    groups.get(key).reviews.push(review);
  }
  return [...groups.values()];
}

function ReviewBody({ review }) {
  return (
    <>
      <div className="my-review-meta">
        <Stars value={review.rating} size="sm" />
        {review.module_code && <Pill variant="accent" size="sm">{review.module_code}</Pill>}
      </div>
      {review.comment
        ? <p className="my-review-comment">{review.comment}</p>
        : <p className="my-review-comment is-empty">No written review</p>}
    </>
  );
}

export default function MyReviewsModal({ onClose, onSelectProfessor, onChanged }) {
  const [reloadKey, setReloadKey] = useState(0);
  const [loaded, setLoaded] = useState({ key: null, reviews: [], deleted: [], error: '' });
  const [confirmingId, setConfirmingId] = useState(null);
  // The cached copy of a review just deleted, while we ask whether to rewrite it
  const [justDeleted, setJustDeleted] = useState(null);
  const [rewriting, setRewriting] = useState(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState('');

  const loading = loaded.key !== reloadKey;
  const reload = () => setReloadKey((k) => k + 1);

  useEffect(() => {
    let cancelled = false;
    Promise.all([fetchMyReviews(), fetchDeletedReviews()])
      .then(([reviews, deleted]) => {
        if (!cancelled) setLoaded({ key: reloadKey, reviews, deleted, error: '' });
      })
      .catch((err) => {
        if (!cancelled) setLoaded({ key: reloadKey, reviews: [], deleted: [], error: err.message });
      });
    return () => { cancelled = true; };
  }, [reloadKey]);

  const run = async (action) => {
    setBusy(true);
    setActionError('');
    try {
      await action();
    } catch (err) {
      setActionError(err.message);
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = (reviewId) => run(async () => {
    const cached = await deleteMyReview(reviewId);
    setConfirmingId(null);
    setJustDeleted(cached);
    reload();
    onChanged?.();
  });

  const handleDiscard = (deletedId) => run(async () => {
    await discardDeletedReview(deletedId);
    if (justDeleted?.id === deletedId) setJustDeleted(null);
    reload();
  });

  const startRewrite = (cached) => {
    setJustDeleted(null);
    setRewriting(cached);
  };

  if (rewriting) {
    // ReviewForm brings its own padding, so no .my-reviews wrapper here
    return (
      <div>
        <ReviewForm
          professorId={rewriting.professor.id}
          professorName={rewriting.professor.name}
          rewriteOf={rewriting}
          onSubmitted={() => {
            setRewriting(null);
            reload();
            onChanged?.();
          }}
          onCancel={() => {
            // The cached copy stays under "Recently deleted" until it expires
            setRewriting(null);
            reload();
          }}
        />
      </div>
    );
  }

  const groups = groupByProfessor(loaded.reviews);
  const otherDeleted = loaded.deleted.filter((d) => d.id !== justDeleted?.id);

  return (
    <div className="my-reviews">
      <div className="my-reviews-header">
        <div>
          <h2>My Reviews</h2>
          <p>
            {loading
              ? 'Loading…'
              : `${loaded.reviews.length} ${loaded.reviews.length === 1 ? 'review' : 'reviews'} of ${groups.length} ${groups.length === 1 ? 'professor' : 'professors'}. `}
            Posted reviews can't be edited. Delete one to write a new version.
          </p>
        </div>
        <button className="my-reviews-close" onClick={onClose} aria-label="Close">✕</button>
      </div>

      {(loaded.error || actionError) && <div className="my-reviews-error">{loaded.error || actionError}</div>}

      {justDeleted && (
        <div className="rewrite-prompt" role="status">
          <p className="rewrite-prompt-title">Review deleted. Do you want to edit it?</p>
          <p className="rewrite-prompt-text">
            We've kept a copy of your review of <strong>{justDeleted.professor.name}</strong> for 24 hours, so you can start from what you wrote.
          </p>
          <div className="rewrite-prompt-actions">
            <Button variant="ghost" size="sm" onClick={() => handleDiscard(justDeleted.id)} disabled={busy}>
              No, delete it
            </Button>
            <Button variant="primary" size="sm" onClick={() => startRewrite(justDeleted)} disabled={busy}>
              Yes, edit it 
            </Button>
          </div>
        </div>
      )}

      {otherDeleted.length > 0 && (
        <section className="my-reviews-section">
          <h3 className="my-reviews-section-title">Recently deleted</h3>
          {otherDeleted.map((d) => (
            <div key={d.id} className="my-review-card is-deleted">
              <div className="my-review-top">
                <span className="deleted-prof">{d.professor.name}</span>
                <span className="my-review-date">Kept for {hoursLeft(d.expires_at)} more h</span>
              </div>
              <ReviewBody review={d} />
              <div className="my-review-actions">
                <Button variant="ghost" size="sm" onClick={() => handleDiscard(d.id)} disabled={busy}>Discard</Button>
                <Button variant="secondary" size="sm" onClick={() => startRewrite(d)} disabled={busy}>Change & repost</Button>
              </div>
            </div>
          ))}
        </section>
      )}

      {loading ? (
        <div className="my-reviews-loading">
          <div className="skeleton" style={{ height: 96, borderRadius: 16 }} />
          <div className="skeleton" style={{ height: 96, borderRadius: 16 }} />
        </div>
      ) : groups.length === 0 ? (
        <div className="my-reviews-empty">
          <p>You haven't posted any reviews yet.</p>
          <span>Pick a professor from the list and click "Write a Review".</span>
        </div>
      ) : (
        groups.map(({ professor, reviews }) => (
          <section key={professor.id} className="my-reviews-section">
            <button
              type="button"
              className="my-reviews-prof"
              onClick={() => onSelectProfessor(professor.id)}
              title="Open this professor"
            >
              <span className="my-reviews-prof-avatar">{professor.name.charAt(0)}</span>
              <span className="my-reviews-prof-text">
                <span className="my-reviews-prof-name">{professor.name}</span>
                {professor.department && <span className="my-reviews-prof-dept">{professor.department}</span>}
              </span>
              <span className="my-reviews-prof-count">{reviews.length}</span>
            </button>

            {reviews.map((review) => (
              <div key={review.id} className="my-review-card">
                <div className="my-review-top">
                  <span className="my-review-date">{formatDate(review.created_at)}</span>
                </div>
                <ReviewBody review={review} />
                <div className="my-review-actions">
                  {confirmingId === review.id ? (
                    <>
                      <span className="confirm-text">Delete this review?</span>
                      <Button variant="ghost" size="sm" onClick={() => setConfirmingId(null)} disabled={busy}>Cancel</Button>
                      <Button variant="danger" size="sm" onClick={() => handleDelete(review.id)} loading={busy}>Delete</Button>
                    </>
                  ) : (
                    <Button variant="ghost" size="sm" onClick={() => setConfirmingId(review.id)} disabled={busy}>Delete</Button>
                  )}
                </div>
              </div>
            ))}
          </section>
        ))
      )}
    </div>
  );
}
