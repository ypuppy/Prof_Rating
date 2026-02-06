import './Pill.css';

export default function Pill({ 
  children, 
  variant = 'default',
  size = 'md',
  icon,
  className = ''
}) {
  const classes = [
    'pill',
    `pill--${variant}`,
    `pill--${size}`,
    className
  ].filter(Boolean).join(' ');

  return (
    <span className={classes}>
      {icon && <span className="pill-icon">{icon}</span>}
      {children}
    </span>
  );
}