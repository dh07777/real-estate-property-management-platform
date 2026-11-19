import { useState } from "react";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { useFetch, Stars, Field, Chip, fdate, useToast } from "../ui";

export function Reviews({ propertyId }) {
  const { user } = useAuth();
  const toast = useToast();
  const f = useFetch(() => api.get(`/properties/${propertyId}/reviews`), [propertyId]);
  const [form, setForm] = useState({ rating: 5, agent_rating: 5, comment: "" });
  const canReview = user && ["buyer", "tenant", "owner"].includes(user.role);
  const submit = async (e) => {
    e.preventDefault();
    try { await api.post(`/properties/${propertyId}/reviews`, { ...form, rating: Number(form.rating), agent_rating: Number(form.agent_rating) }); toast("Review posted"); setForm({ ...form, comment: "" }); f.reload(); } catch (er) { toast(errMsg(er), "err"); }
  };
  const report = async (r) => {
    try { await api.post(`/reviews/${r.id}/report`, { reason: "Reported by user" }); toast("Reported to moderators"); f.reload(); } catch (er) { toast(errMsg(er), "err"); }
  };
  const sum = f.meta?.summary, ag = f.meta?.agent;
  return (
    <section className="card">
      <h3>Reviews {sum?.average && <><Stars n={sum.average} /> {sum.average} ({sum.count})</>}</h3>
      {ag?.average && <p className="muted">Agent {ag.name}: <Stars n={ag.average} /> {ag.average} from {ag.count} rating(s)</p>}
      {f.data?.length === 0 && <p className="muted">No reviews yet.</p>}
      {f.data?.map((r) => <div key={r.id} style={{ borderTop: "1px solid var(--line)", padding: "8px 0" }}>
        <Stars n={r.rating} /> <strong>{r.reviewer}</strong> {r.verified && <Chip v="verified" />} <span className="muted">{fdate(r.created_at)}</span>
        <p>{r.comment}</p>{user && r.status !== "reported" && <button className="btn sm" onClick={() => report(r)}>Report</button>}{r.status === "reported" && <span className="muted">Under review</span>}</div>)}
      {canReview && <form className="filters" onSubmit={submit}>
        <Field label="Property rating"><select value={form.rating} onChange={(e) => setForm({ ...form, rating: e.target.value })}>{[5, 4, 3, 2, 1].map((n) => <option key={n}>{n}</option>)}</select></Field>
        <Field label="Agent rating"><select value={form.agent_rating} onChange={(e) => setForm({ ...form, agent_rating: e.target.value })}>{[5, 4, 3, 2, 1].map((n) => <option key={n}>{n}</option>)}</select></Field>
        <Field label="Comment"><input value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} /></Field>
        <button className="btn primary">Post review</button></form>}
    </section>
  );
}
