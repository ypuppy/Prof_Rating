import { useState } from 'react';
import './StaffInfo.css';

const BIO_PREVIEW_CHARS = 220;

function hostLabel(url) {
  try {
    const { hostname, pathname } = new URL(url);
    const host = hostname.replace(/^www\./, '');
    if (host === 'discovery.nus.edu.sg') return 'NUS Discovery profile';
    if (host === 'fass.nus.edu.sg' && pathname.includes('/people/')) return 'Department profile';
    return host;
  } catch {
    return url;
  }
}

/** What the department website says about a professor. */
export default function StaffInfo({ staff }) {
  const [expanded, setExpanded] = useState(false);
  const longBio = staff.bio && staff.bio.length > BIO_PREVIEW_CHARS;
  const bio = longBio && !expanded ? `${staff.bio.slice(0, BIO_PREVIEW_CHARS).trimEnd()}…` : staff.bio;

  return (
    <div className="staff-info">
      {(staff.position || staff.roles.length > 0) && (
        <p className="staff-position">{[staff.position, ...staff.roles].filter(Boolean).join(' · ')}</p>
      )}

      {staff.research_areas && (
        <div className="staff-row">
          <span className="staff-label">Research areas</span>
          <span>{staff.research_areas}</span>
        </div>
      )}

      {bio && (
        <div className="staff-row">
          <span className="staff-label">About</span>
          <span>
            {bio}{' '}
            {longBio && (
              <button type="button" className="staff-more" onClick={() => setExpanded((e) => !e)}>
                {expanded ? 'Show less' : 'Read more'}
              </button>
            )}
          </span>
        </div>
      )}

      {staff.profile_urls.length > 0 && (
        <div className="staff-row">
          <span className="staff-label">Links</span>
          <span className="staff-links">
            {staff.profile_urls.map((url) => (
              <a key={url} href={url} target="_blank" rel="noopener noreferrer">{hostLabel(url)}</a>
            ))}
          </span>
        </div>
      )}

      <p className="staff-source">
        From the{' '}
        <a href={staff.source_url} target="_blank" rel="noopener noreferrer">
          {staff.department ? `Department of ${staff.department}` : 'department'} website
        </a>
      </p>
    </div>
  );
}
