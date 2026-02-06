import Card from '../../components/Card';
import Stars from '../../components/stars';
import Pill from '../../components/Pill';
import './ProfessorList.css';

export default function ProfessorList({ 
  items = [], 
  selectedId, 
  onSelect,
  loading = false 
}) {
  if (loading) {
    return (
      <div className="professor-list">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="skeleton skeleton-card" />
        ))}
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="professor-list-empty">
        <div className="empty-icon">👨‍🏫</div>
        <p>No professors found</p>
      </div>
    );
  }

  return (
    <div className="professor-list stagger-children">
      {items.map((professor) => {
        const isActive = professor.id === selectedId;
        
        return (
          <Card
            key={professor.id}
            className="professor-card"
            hoverable
            active={isActive}
            onClick={() => onSelect(professor.id)}
             style={{ border: '1px solid blue' }} 
          >
            <div className="professor-card-content">
              <div className="professor-info">
                <div className="professor-avatar">
                  {professor.name?.charAt(0) || '?'}
                </div>
                <div className="professor-details">
                  <h3 className="professor-name">{professor.name}</h3>
                  <p className="professor-meta">
                    {professor.department || 'Unknown Department'}
                    {professor.faculty && (
                      <span className="meta-separator">·</span>
                    )}
                    {professor.faculty}
                  </p>
                </div>
              </div>
              
              <div className="professor-rating">
                {professor.avg_rating ? (
                  <>
                    <Stars value={professor.avg_rating} size="sm" />
                    <span className="rating-value">{professor.avg_rating.toFixed(1)}</span>
                  </>
                ) : (
                  <Pill variant="outline" size="sm">No reviews</Pill>
                )}
              </div>
            </div>
          </Card>
        );
      })}
    </div>
  );
}