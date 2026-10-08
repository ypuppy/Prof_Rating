import { useState } from 'react';
import { createProfessor } from '../../api/professors';
import Button from '../../components/Button';
import Autocomplete from '../../components/Autocomplete';
import { searchDepartments, searchFaculties } from '../../api/reference';
import { useAuth } from '../auth/AuthContext';
import './AddProfessorForm.css';

export default function AddProfessorForm({ onSuccess, onCancel }) {
  const [name, setName] = useState('');
  const [department, setDepartment] = useState('');
  const [faculty, setFaculty] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const { promptLogin } = useAuth();

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
      });

      // Success - clear form and notify parent
      setName('');
      setDepartment('');
      setFaculty('');
      onSuccess?.(data);
    } catch (err) {
      if (err.status === 401) promptLogin();
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
          <input
            id="profName"
            type="text"
            className="form-input"
            placeholder="e.g. Dr. John Smith"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
          />
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
          <Button type="submit" variant="primary" loading={loading}>
            Add Professor
          </Button>
        </div>
      </form>
    </div>
  );
}