import { useEffect, useRef, useState } from 'react';
import { createProfessor, findSimilarProfessors } from '../../api/professors';
import Button from '../../components/Button';
import Autocomplete from '../../components/Autocomplete';
import { searchDepartments, searchFaculties } from '../../api/reference';
import { searchStaff } from '../../api/staff';
import Avatar from '../../components/Avatar';
import { useAuth } from '../auth/AuthContext';
import './AddProfessorForm.css';

const CHECK_DELAY_MS = 300;

export default function AddProfessorForm({ onSuccess, onCancel, onOpenExisting }) {
  const [name, setName] = useState('');
  const [department, setDepartment] = useState('');
  const [faculty, setFaculty] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { promptLogin } = useAuth();
  // Existing professors who may be this person, from /professors/similar
  const [similar, setSimilar] = useState([]);
  const [differentPerson, setDifferentPerson] = useState(false);
  // The department-website entry picked from the name suggestions, if any
  const [staff, setStaff] = useState(null);
  const checkTimer = useRef(null);
  const latestCheck = useRef(0);

  useEffect(() => () => clearTimeout(checkTimer.current), []);

  const hasSame = similar.some((p) => p.match === 'same');
  const needsConfirm = similar.length > 0 && !hasSame;
  const blocked = hasSame || (needsConfirm && !differentPerson);

  const checkName = (value) => {
    clearTimeout(checkTimer.current);
    if (value.trim().length < 3) {
      latestCheck.current++; // drop any check still in flight
      setSimilar([]);
      return;
    }
    checkTimer.current = setTimeout(async () => {
      const checkId = ++latestCheck.current;
      try {
        const results = await findSimilarProfessors(value.trim());
        if (checkId === latestCheck.current) setSimilar(results);
      } catch {
        // The server still checks on submit, so a failed lookup isn't fatal
      }
    }, CHECK_DELAY_MS);
  };

  const handleNameChange = (value) => {
    setName(value);
    setDifferentPerson(false); // a new name needs a new confirmation
    if (staff && value.trim() !== staff.name) setStaff(null); // edited away from the website's name
    checkName(value);
  };

  const handlePickStaff = (person) => {
    if (person.professor_id) {
      // Already has a page here: go there instead of adding them again
      onOpenExisting?.(person.professor_id);
      return;
    }
    setStaff(person);
    setName(person.name);
    setDepartment(person.department || '');
    setFaculty(person.faculty || '');
    setDifferentPerson(false);
    checkName(person.name);
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    
    if (!name.trim()) {
      setError('Professor name is required');
      return;
    }

    setLoading(true);
    setError('');

    try {
      const data = await createProfessor({
        name: name.trim(),
        department: department.trim() || null,
        faculty: faculty.trim() || null,
        confirm_not_duplicate: differentPerson,
        staff_id: staff?.id ?? null,
      });

      // Success - clear form and notify parent
      setName('');
      setDepartment('');
      setFaculty('');
      setStaff(null);
      onSuccess?.(data);
    } catch (err) {
      if (err.status === 401) promptLogin();
      // 409: the server found a match (maybe added since our last check); show it
      const serverSimilar = err.data?.detail?.similar;
      if (err.status === 409 && Array.isArray(serverSimilar)) {
        setSimilar(serverSimilar);
        setError('');
        return;
      }
      setError(err.status === 401 ? 'Your session expired. Log in, then submit again.' : err.message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="add-professor-form">
      <div className="form-header">
        <h2>Add New Professor</h2>
        <p>Add a professor to the database</p>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label className="form-label" htmlFor="profName">
            Name *
          </label>
          <Autocomplete
            id="profName"
            placeholder="Start typing, e.g. Moonyoung Song"
            value={name}
            onChange={handleNameChange}
            fetchSuggestions={searchStaff}
            renderItem={(p) => ({
              primary: p.name,
              secondary: [
                p.position,
                p.department,
                p.professor_id ? 'Already on ProfRating: open page' : null,
              ].filter(Boolean).join(' · '),
            })}
            onSelect={handlePickStaff}
            minChars={2}
            maxLength={120}
            autoFocus
          />
          {staff && (
            <div className="staff-linked">
              <Avatar className="staff-linked-avatar" name={staff.name} photoUrl={staff.photo_url} />
              <span className="staff-linked-text">
                <span className="staff-linked-title">Linked to the department website</span>
                <span className="staff-linked-meta">
                  {[staff.position, staff.department].filter(Boolean).join(' · ')}
                </span>
              </span>
              <button type="button" className="staff-linked-remove" onClick={() => setStaff(null)}>
                Unlink
              </button>
            </div>
          )}
          {similar.length > 0 && (
            <div className={`duplicate-panel${hasSame ? ' is-same' : ''}`} role="status">
              <p className="duplicate-title">
                {hasSame ? 'This professor is already on ProfRating' : 'Is this the same person?'}
              </p>
              <ul className="duplicate-list">
                {similar.map((p) => (
                  <li key={p.id} className="duplicate-item">
                    <span className="duplicate-text">
                      <span className="duplicate-name">{p.name}</span>
                      <span className="duplicate-meta">
                        {[p.department, p.faculty].filter(Boolean).join(' · ') || 'No department'}
                        {' · '}
                        {p.review_count} {p.review_count === 1 ? 'review' : 'reviews'}
                      </span>
                    </span>
                    <Button type="button" variant="secondary" size="sm" onClick={() => onOpenExisting?.(p.id)}>
                      Open
                    </Button>
                  </li>
                ))}
              </ul>
              {needsConfirm && (
                <label className="duplicate-confirm">
                  <input
                    id="profDifferentPerson"
                    type="checkbox"
                    checked={differentPerson}
                    onChange={(e) => setDifferentPerson(e.target.checked)}
                  />
                  None of these. This is a different person.
                </label>
              )}
            </div>
          )}
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="profDept">
            Department
            <span className="label-hint">(optional)</span>
          </label>
          <Autocomplete
            id="profDept"
            placeholder="e.g. Computer Science"
            value={department}
            onChange={setDepartment}
            fetchSuggestions={(q) => searchDepartments(q, faculty.trim() || undefined)}
            renderItem={(d) => ({ primary: d.name, secondary: d.faculty })}
            onSelect={(d) => {
              setDepartment(d.name);
              // Picking a department fills in its faculty, unless the user already chose one
              if (!faculty.trim() && d.faculty) setFaculty(d.faculty);
            }}
            maxLength={120}
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="profFaculty">
            Faculty
            <span className="label-hint">(optional)</span>
          </label>
          <Autocomplete
            id="profFaculty"
            placeholder="e.g. School of Computing"
            value={faculty}
            onChange={setFaculty}
            fetchSuggestions={searchFaculties}
            renderItem={(f) => ({ primary: f.name, secondary: f.short_name })}
            onSelect={(f) => setFaculty(f.name)}
            maxLength={120}
          />
        </div>

        {error && (
          <div className="form-error">
            {error}
          </div>
        )}

        <div className="form-actions">
          <Button type="button" variant="ghost" onClick={onCancel}>
            Cancel
          </Button>
          <Button type="submit" variant="primary" loading={loading} disabled={blocked}>
            {needsConfirm ? 'Add anyway' : 'Add Professor'}
          </Button>
        </div>
      </form>
    </div>
  );
}