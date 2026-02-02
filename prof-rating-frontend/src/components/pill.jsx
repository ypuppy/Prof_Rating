export default function Pill({ children }) {
  return (
    <span
      style={{
        padding: "4px 10px",
        borderRadius: 999,
        border: "1px solid #e6e6e6",
        background: "#fafafa",
        fontSize: 12,
      }}
    >
      {children}
    </span>
  );
}
