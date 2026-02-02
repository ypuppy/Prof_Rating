export default function ProfessorList({ items, selectedId, onSelect }) {
  return (
    <div style={{ display: "grid", gap: 10 }}>
      {items.map((p) => {
        const active = p.id === selectedId;
        return (
          <button
            key={p.id}
            onClick={() => onSelect(p.id)}
            style={{
              textAlign: "left",
              padding: 12,
              borderRadius: 14,
              border: active ? "1px solid #111" : "1px solid #eee",
              background: active ? "#111" : "#fff",
              color: active ? "#fff" : "#111",
            }}
          >
            <div style={{ fontWeight: 800 }}>{p.name}</div>
            <div style={{ fontSize: 13, opacity: 0.7 }}>
              {p.department || "—"} · {p.faculty || "—"}
            </div>
          </button>
        );
      })}
    </div>
  );
}
