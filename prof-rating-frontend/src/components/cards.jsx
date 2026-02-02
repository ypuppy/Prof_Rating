export default function Card({ children, style }) {
  return (
    <div
      style={{
        border: "1px solid #eee",
        borderRadius: 16,
        background: "#fff",
        boxShadow: "0 6px 18px rgba(0,0,0,0.04)",
        ...style,
      }}
    >
      {children}
    </div>
  );
}
