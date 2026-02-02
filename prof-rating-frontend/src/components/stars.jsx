export default function Stars({ value = 0 }) {
  const v = Math.max(0, Math.min(5, Number(value)));
  return (
    <span>
      {[1, 2, 3, 4, 5].map((i) => (
        <span key={i} style={{ opacity: i <= v ? 1 : 0.25 }}>★</span>
      ))}
    </span>
  );
}
