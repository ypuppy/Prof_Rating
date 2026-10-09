import { useState } from 'react';
import './Avatar.css';

/**
 * A professor's photo, or their initial when there's no photo or it fails to load
 * (the department site may refuse hotlinked images).
 */
export default function Avatar({ name, photoUrl, className = '' }) {
  const [failedUrl, setFailedUrl] = useState(null);
  const showPhoto = photoUrl && failedUrl !== photoUrl;

  return (
    <div className={`avatar ${className}`}>
      {showPhoto ? (
        <img
          src={photoUrl}
          alt=""
          loading="lazy"
          referrerPolicy="no-referrer"
          onError={() => setFailedUrl(photoUrl)}
        />
      ) : (
        name?.charAt(0) || '?'
      )}
    </div>
  );
}
