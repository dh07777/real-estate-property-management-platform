import { useEffect, useState } from "react";
import api, { errMsg } from "../api";
import { useAuth, ADMINS } from "../auth";
import { useFetch, State, Empty, Chip, Field, Stars, fdate, useToast } from "../ui";

export function Vendors() {
  const toast = useToast();
  const f = useFetch(() => api.get("/vendors"), []);
  const [v, setV] = useState({ name: "", category: "plumbing", phone: "", email: "" });
  const act = async (fn, msg) => { try { await fn(); toast(msg); f.reload(); return true; } catch (e) { toast(errMsg(e), "err"); return false; } };
  return (
    <>
      <h1>Vendors</h1>
      <form className="card filters" onSubmit={async (e) => { e.preventDefault(); (await act(() => api.post("/vendors", v), "Vendor added")) && setV({ ...v, name: "", phone: "", email: "" }); }}>
        <Field label="Name"><input required value={v.name} onChange={(e) => setV({ ...v, name: e.target.value })} /></Field>
        <Field label="Category"><select value={v.category} onChange={(e) => setV({ ...v, category: e.target.value })}>{["plumbing", "electrical", "appliance", "structural", "cleaning", "other"].map((c) => <option key={c}>{c}</option>)}</select></Field>
        <Field label="Phone"><input value={v.phone} onChange={(e) => setV({ ...v, phone: e.target.value })} /></Field>
        <Field label="Email"><input type="email" value={v.email} onChange={(e) => setV({ ...v, email: e.target.value })} /></Field>
        <button className="btn primary">Add vendor</button></form>
      <State f={f} empty={<Empty title="No vendors yet" />}>
        <div className="card tablewrap"><table><thead><tr><th>Name</th><th>Category</th><th>Phone</th><th>Email</th><th>Status</th><th></th></tr></thead><tbody>
          {f.data?.map((x) => <tr key={x.id}><td>{x.name}</td><td>{x.category}</td><td>{x.phone}</td><td>{x.email}</td><td><Chip v={x.active ? "active" : "cancelled"} /></td><td><button className="btn sm" onClick={() => act(() => api.patch(`/vendors/${x.id}`, { active: !x.active }), x.active ? "Vendor deactivated" : "Vendor activated")}>{x.active ? "Deactivate" : "Activate"}</button></td></tr>)}</tbody></table></div>
      </State>
    </>
  );
}

export function Moderation() {
  const toast = useToast();
  const [status, setStatus] = useState("reported");
  const f = useFetch(() => api.get("/admin/reviews", { params: { status } }), [status]);
  const set = async (r, st) => { try { await api.patch(`/admin/reviews/${r.id}`, { status: st }); toast(st === "hidden" ? "Review hidden" : "Review restored"); f.reload(); } catch (e) { toast(errMsg(e), "err"); } };
  return (
    <>
      <div className="row between"><h1>Review moderation</h1><select aria-label="Status" value={status} onChange={(e) => setStatus(e.target.value)}><option value="reported">Reported</option><option value="hidden">Hidden</option><option value="published">Published</option></select></div>
      <State f={f} empty={<Empty title="Nothing to moderate" />}>
        {f.data?.map((r) => <div key={r.id} className="card"><div className="row between wrap gap"><div><Stars n={r.rating} /> <strong>{r.reviewer}</strong> on {r.property_title} {r.verified && <Chip v="verified" />}<div className="muted">{fdate(r.created_at)}{r.report_reason && ` · Reported: ${r.report_reason}`}</div></div>
          <div className="row gap">{r.status !== "hidden" && <button className="btn sm danger" onClick={() => set(r, "hidden")}>Hide</button>}{r.status !== "published" && <button className="btn sm" onClick={() => set(r, "published")}>Restore</button>}</div></div><p>{r.comment}</p></div>)}
      </State>
    </>
  );
}

export function Settings() {
  const { user } = useAuth();
  const toast = useToast();
  const s = useFetch(() => api.get("/settings"), []);
  const ag = useFetch(() => api.get("/agencies"), []);
  const [f, setF] = useState(null);
  const [agency, setAgency] = useState({ name: "", city: "" });
  const [staff, setStaff] = useState([]);
  const [assign, setAssign] = useState({ agency: "", user: "" });
  useEffect(() => { if (s.data) setF(s.data); }, [s.data]);
  useEffect(() => { Promise.all(["agent"].map((r) => api.get("/users/lookup", { params: { role: r } }))).then(([a]) => setStaff(a.data.data)).catch(() => {}); }, []);
  const save = async (e) => { e.preventDefault(); try { await api.put("/settings", f); toast("Settings saved"); } catch (er) { toast(errMsg(er), "err"); } };
  const addAgency = async (e) => { e.preventDefault(); try { await api.post("/agencies", agency); toast("Agency created"); setAgency({ name: "", city: "" }); ag.reload(); } catch (er) { toast(errMsg(er), "err"); } };
  const addMember = async () => { try { const r = await api.put(`/agencies/${assign.agency}/members`, { user_id: Number(assign.user) }); toast(r.data.data.message); ag.reload(); } catch (er) { toast(errMsg(er), "err"); } };
  const tog = (k) => setF({ ...f, [k]: f[k] === "1" ? "0" : "1" });
  return (
    <>
      <h1>Settings</h1>
      <div className="grid g2">
        <State f={s}>{f && <form className="card form" onSubmit={save}>
          <h3>Platform</h3>
          <Field label="Platform name"><input value={f.platform_name} onChange={(e) => setF({ ...f, platform_name: e.target.value })} /></Field>
          <Field label="Support email"><input type="email" value={f.support_email} onChange={(e) => setF({ ...f, support_email: e.target.value })} /></Field>
          <Field label="Default agent commission (%)"><input type="number" step="0.1" min="0" max="20" value={f.default_commission_rate} onChange={(e) => setF({ ...f, default_commission_rate: e.target.value })} /></Field>
          <label className="row gap"><input type="checkbox" style={{ width: "auto" }} checked={f.allow_registration === "1"} onChange={() => tog("allow_registration")} /> Allow public registration</label>
          <label className="row gap"><input type="checkbox" style={{ width: "auto" }} checked={f.notifications_enabled === "1"} onChange={() => tog("notifications_enabled")} /> In-app notifications enabled</label>
          <button className="btn primary">Save settings</button></form>}</State>
        <div className="card"><h3>Agencies</h3>
          <State f={ag} empty={<Empty title="No agencies" />}>{ag.data?.map((a) => <p key={a.id} className="row between"><span>{a.name} <span className="muted">{a.city}</span></span><span className="muted">{a.members} member(s)</span></p>)}</State>
          {ADMINS.includes(user.role) && <><form className="form" onSubmit={addAgency}><Field label="New agency"><input required value={agency.name} onChange={(e) => setAgency({ ...agency, name: e.target.value })} /></Field><Field label="City"><input value={agency.city} onChange={(e) => setAgency({ ...agency, city: e.target.value })} /></Field><button className="btn">Create agency</button></form>
            <div className="form" style={{ marginTop: 12 }}><Field label="Add agent to agency"><select value={assign.agency} onChange={(e) => setAssign({ ...assign, agency: e.target.value })}><option value="">Agency</option>{ag.data?.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></Field>
              <select aria-label="Agent" value={assign.user} onChange={(e) => setAssign({ ...assign, user: e.target.value })}><option value="">Agent</option>{staff.map((u) => <option key={u.id} value={u.id}>{u.name}</option>)}</select>
              <button className="btn" disabled={!assign.agency || !assign.user} onClick={addMember}>Assign</button></div></>}
        </div>
      </div>
    </>
  );
}
