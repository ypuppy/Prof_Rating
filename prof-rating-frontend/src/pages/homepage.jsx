import { useEffect, useState } from "react";
import { fetchProfessors, fetchProfessorDetail } from "../api/professors";
import { fetchReviews } from "../api/reviews";
import ProfessorList from "../features/professors/ProfessorList";

export default function HomePage() {
  const [professors, setProfessors] = useState([]);
  const [selectedId, setSelectedId] = useState(null);

  useEffect(() => {
    fetchProfessors().then(setProfessors);
  }, []);

  return (
    <div>
      <ProfessorList
        items={professors}
        selectedId={selectedId}
        onSelect={setSelectedId}
      />
    </div>
  );
}
