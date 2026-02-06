import { useState } from 'react';
import './stars.css';

export default function Stars({ 
  value = 0, 
  max = 5,
  size = 'md',
  interactive = false,
  onChange,
  showValue = false 
}) {
  const [hoverValue, setHoverValue] = useState(0);
  const displayValue = hoverValue || value;
  const normalizedValue = Math.max(0, Math.min(max, Number(displayValue)));

  const handleClick = (rating) => {
    if (interactive && onChange) {
      onChange(rating);
    }
  };

  const handleMouseEnter = (rating) => {
    if (interactive) {
      setHoverValue(rating);
    }
  };

  const handleMouseLeave = () => {
    if (interactive) {
      setHoverValue(0);
    }
  };

  return (
    <div className={`stars stars--${size} ${interactive ? 'stars--interactive' : ''}`}>
      <div className="stars-container" onMouseLeave={handleMouseLeave}>
        {[...Array(max)].map((_, i) => {
          const rating = i + 1;
          const isFilled = rating <= normalizedValue;
          const isPartial = !isFilled && rating - 1 < normalizedValue;
          const partialWidth = isPartial ? (normalizedValue - (rating - 1)) * 100 : 0;

          return (
            <span
              key={i}
              className={`star ${isFilled ? 'star--filled' : ''} ${isPartial ? 'star--partial' : ''}`}
              onClick={() => handleClick(rating)}
              onMouseEnter={() => handleMouseEnter(rating)}
              role={interactive ? 'button' : undefined}
              tabIndex={interactive ? 0 : undefined}
              onKeyDown={interactive ? (e) => e.key === 'Enter' && handleClick(rating) : undefined}
              style={isPartial ? { '--partial-width': `${partialWidth}%` } : undefined}
            >
              ★
            </span>
          );
        })}
      </div>
      {showValue && value > 0 && (
        <span className="stars-value">{value.toFixed(1)}</span>
      )}
    </div>
  );
}