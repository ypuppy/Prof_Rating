import { useState } from 'react';
import { createProfessor } from '../../api/professors';
import Button from '../../components/Button';
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
          <input
            id="profDept"
            type="text"
            className="form-input"
            placeholder="e.g. Computer Science"
            value={department}
            onChange={(e) => setDepartment(e.target.value)}
          />
        </div>

        <div className="form-group">
          <label className="form-label" htmlFor="profFaculty">
            Faculty
            <span className="label-hint">(optional)</span>
          </label>
          <input
            id="profFaculty"
            type="text"
            className="form-input"
            placeholder="e.g. School of Computing"
            value={faculty}
            onChange={(e) => setFaculty(e.target.value)}
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