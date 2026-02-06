import './Card.css';

export default function Card({ 
  children, 
  className = '', 
  variant = 'default',
  hoverable = false,
  active = false,
  onClick,
  style 
}) {
  const classes = [
    'card',
    `card--${variant}`,
    hoverable && 'card--hoverable',
    active && 'card--active',
    className
  ].filter(Boolean).join(' ');

  return (
    <div 
      className={classes}
      onClick={onClick}
      style={style}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => e.key === 'Enter' && onClick(e) : undefined}
    >
      {children}
    </div>
  );
}