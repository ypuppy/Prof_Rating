import { createReview } from "../../api/reviews";

export default function ReviewForm({ professorId, onSubmitted }) {
  const [rating, setRating] = useState(0);
  const [comment, setComment] = useState("");
  const [loading, setLoading] = useState(false);

  async function submit() {
    if (rating < 1) return alert("Please select rating");

    setLoading(true);
    await createReview(professorId, { rating, comment });
    setRating(0);
    setComment("");
    setLoading(false);
    onSubmitted();
  }

  return (
    <div>
      {/* simplified for now */}
      <button onClick={submit} disabled={loading}>Submit</button>
    </div>
  );
}
