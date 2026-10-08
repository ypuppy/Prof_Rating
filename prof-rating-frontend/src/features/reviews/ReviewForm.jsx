import { useState } from 'react';
import { createReview } from '../../api/reviews';
import Stars from '../../components/stars';
import Button from '../../components/Button';
import Autocomplete from '../../components/Autocomplete';
import { searchModules } from '../../api/reference';
import { SEMESTERS, academicYearOptions, formatAcademicYear } from '../../utils/terms';
import { useAuth } from '../auth/AuthContext';
import './ReviewForm.css';

export default function ReviewForm({ 
  professorId, 
  professorName,
  onSubmitted, 
  onCancel,
  // Rewriting a deleted review: pre-fill its content and clear it from the cache on submit
  rewriteOf = null,
}) {
  const [rating, setRating] = useState(rewriteOf?.rating ?? 0);
  const [moduleCode, setModuleCode] = useState(rewriteOf?.module_code ?? '');
  const [comment, setComment] = useState(rewriteOf?.comment ?? '');
  // Kept as strings because <select> values are strings; '' means "not chosen yet"
  const [academicYear, setAcademicYear] = useState(rewriteOf?.academic_year ? String(rewriteOf.academic_year) : '');
  const [semester, setSemester] = useState(rewriteOf?.semester ? String(rewriteOf.semester) : '');
  // A review being rewritten may be from further back than the default range
  const yearOptions = [...new Set([...academicYearOptions(), rewriteOf?.academic_year].filter(Boolean))]
    .sort((a, b) => b - a);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { promptLogin } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (rating < 1) {
      setError('Please select a rating');
      return;
    }
    if (!academicYear || !semester) {
      setError('Please select when you took this class');
      return;
    }

    setLoading(true);
    setError('');
    
    try {
      await createReview(professorId, { 
        rating, 
        module_code: moduleCode || null,
        comment: comment || null,
        academic_year: Number(academicYear),
        semester: Number(semester),
        replaces_deleted_review_id: rewriteOf?.id ?? null,
      });
      onSubmitted?.();
    } catch (err) {
      if (err.status === 401) promptLogin();
      setError(err.status === 401 ? 'Your session expired. Log in, then submit again.' : err.message || 'Failed to submit review');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="review-form">
      <div className="review-form-header">
        <h2>{rewriteOf ? 'Rewrite Your Review' : 'Write a Review'}</h2>
        {professorName && (
          <p className="review-form-subtitle">for {professorName}</p>
        )}
      </div>

      <form onSubmit={handleSubmit}>
        {/* Rating */}
        <div className="form-group">
          <label className="form-label">Rating *</label>
          <div className="rating-input">
            <Stars 
              value={rating} 
              size="xl" 
              interactive 
              onChange={setRating} 
            />
            {rating > 0 && (
              <span className="rating-text">
                {rating === 1 && 'Poor'}
                {rating === 2 && 'Fair'}
                {rating === 3 && 'Good'}
                {rating === 4 && 'Very Good'}
                {rating === 5 && 'Excellent'}
              </span>
            )}
          </div>
        </div>

        {/* When the class was taken */}
        <div className="form-group">
          <label className="form-label" htmlFor="academicYear">When did you take this class? *</label>
          <div className="term-row">
            <select
              id="academicYear"
              className="form-input"
              value={academicYear}
              onChange={(e) => setAcademicYear(e.target.value)}
              aria-label="Academic year"
            >
              <option value="" disabled>Academic year</option>
              {yearOptions.map((y) => (
                <option key={y} value={y}>{formatAcademicYear(y)}</option>
              ))}
            </select>
            <select
              id="semester"
              className="form-input"
              value={semester}
              onChange={(e) => setSemester(e.target.value)}
              aria-label="Semester"
            >
              <option value="" disabled>Semester</option>
              {SEMESTERS.map((s) => (
                <option key={s.value} value={s.value}>{s.label}</option>
              ))}
            </select>
          </div>
        </div>

        {/* Module Code */}
        <div className="form-group">
          <label className="form-label" htmlFor="moduleCode">
            Module Code
            <span className="label-hint">(optional)</span>
          </label>
          <Autocomplete
            id="moduleCode"
            placeholder="e.g. CS1101S"
            value={moduleCode}
            onChange={setModuleCode}
            fetchSuggestions={searchModules}
            renderItem={(m) => ({ primary: m.code, secondary: m.title })}
            onSelect={(m) => setModuleCode(m.code)}
            minChars={1}
            maxLength={20}
          />
        </div>

        {/* Comment */}
        <div className="form-group">
          <label className="form-label" htmlFor="comment">
            Your Review
            <span className="label-hint">(optional)</span>
          </label>
          <textarea
            id="comment"
            className="form-textarea"
            placeholder="Share your experience with this professor..."
            value={comment}
            onChange={(e) => setComment(e.target.value)}
            rows={4}
            maxLength={1000}
          />
          <div className="char-count">
            {comment.length}/1000
          </div>
        </div>

        {/* Error */}
        {error && (
          <div className="form-error">
            {error}
          </div>
        )}

        {/* Actions */}
        <div className="form-actions">
          <Button 
            type="button" 
            variant="ghost" 
            onClick={onCancel}
          >
            Cancel
          </Button>
          <Button 
            type="submit" 
            variant="primary"
            loading={loading}
          >
            {rewriteOf ? 'Post New Version' : 'Submit Review'}
          </Button>
        </div>
      </form>
    </div>
  );
}