import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import api, { errMsg } from "../api";
import { useAuth, MANAGERS, STAFF } from "../auth";
import { AuthImg, useFetch, State, Empty, Chip, Pager, Modal, Field, PropertyCard, inr, fdate, fdt, useToast } from "../ui";

const LEAD_STATUSES = ["New", "Contacted", "Interested", "Visit Scheduled", "Negotiation", "Converted", "Lost"];

function useAct(reload) {
  const toast = useToast();
  return async (fn, msg) => { try { await fn(); if (msg) toast(msg); reload(); return true; } catch (e) { toast(errMsg(e), "err"); return false; } };
}

export function Inquiries() {
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const [status, setStatus] = useState("");
  const f = useFetch(() => api.get("/inquiries", { params: { page, status: status || undefined, per_page: 10 } }), [page, status]);
  const act = useAct(f.reload);
  const [agents, setAgents] = useState([]);
  const [note, setNote] = useState({});
  const isStaff = STAFF.includes(user.role);
  useEffect(() => { if (MANAGERS.includes(user.role)) api.get("/users/lookup", { params: { role: "agent" } }).then((r) => setAgents(r.data.data)).catch(() => {}); }, [user.role]);
  const patch = (i, body, msg = "Lead updated") => act(() => api.patch(`/inquiries/${i.id}`, body), msg);
  return (
    <>
      <div className="row between wrap gap"><h1>{isStaff ? "Leads and inquiries" : "My inquiries"}</h1>
        <select aria-label="Filter status" value={status} onChange={(e) => { setStatus(e.target.value); setPage(1); }}><option value="">All statuses</option>{LEAD_STATUSES.map((s) => <option key={s}>{s}</option>)}</select></div>
      <State f={f} empty={<Empty title="No inquiries yet" hint="Inquiries from property pages appear here." />}>
        {f.data?.map((i) => <div key={i.id} className="card">
          <div className="row between wrap gap"><div><strong>{i.name}</strong> · <Link to={`/properties/${i.property_id}`}>{i.property_title}</Link><div className="muted">{i.email} {i.phone} · {fdt(i.created_at)} · via {i.source}</div></div><div className="row gap"><Chip v={i.priority} /><Chip v={i.status} /></div></div>
          <p>{i.message}</p>
          {i.notes && <pre className="muted" style={{ whiteSpace: "pre-wrap", fontFamily: "inherit" }}>{i.notes}</pre>}
          {isStaff && <div className="filters">
            <Field label="Status"><select value={i.status} onChange={(e) => patch(i, { status: e.target.value })}>{LEAD_STATUSES.map((s) => <option key={s}>{s}</option>)}</select></Field>
            <Field label="Priority"><select value={i.priority} onChange={(e) => patch(i, { priority: e.target.value })}><option>low</option><option>medium</option><option>high</option></select></Field>
            <Field label="Follow-up"><input type="date" value={i.follow_up_date || ""} onChange={(e) => patch(i, { follow_up_date: e.target.value })} /></Field>
            {MANAGERS.includes(user.role) && <Field label="Assign agent"><select value={i.agent_id || ""} onChange={(e) => e.target.value && patch(i, { agent_id: Number(e.target.value) }, "Lead assigned")}><option value="">Unassigned</option>{agents.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}</select></Field>}
            <Field label="Add note"><input value={note[i.id] || ""} onChange={(e) => setNote({ ...note, [i.id]: e.target.value })} onKeyDown={(e) => e.key === "Enter" && note[i.id] && patch(i, { note: note[i.id] }, "Note added").then(() => setNote({ ...note, [i.id]: "" }))} placeholder="Press Enter to save" /></Field></div>}
        </div>)}
        <Pager meta={f.meta} onPage={setPage} />
      </State>
    </>
  );
}

export function Appointments() {
  const { user } = useAuth();
  const f = useFetch(() => api.get("/appointments", { params: { per_page: 50 } }), []);
  const act = useAct(f.reload);
  const [resched, setResched] = useState(null);
  const [when, setWhen] = useState("");
  const staffLike = STAFF.includes(user.role);
  return (
    <>
      <h1>Property visits</h1>
      <State f={f} empty={<Empty title="No visits scheduled" hint="Book a visit from any property page." />}>
        <div className="card tablewrap"><table><thead><tr><th>When</th><th>Property</th><th>Visitor</th><th>Status</th><th></th></tr></thead><tbody>
          {f.data?.map((a) => <tr key={a.id}><td>{fdt(a.scheduled_at)}</td><td><Link to={`/properties/${a.property_id}`}>{a.property_title}</Link></td><td>{a.visitor}</td><td><Chip v={a.status} /></td>
            <td className="row gap wrap">{!["cancelled", "completed"].includes(a.status) && <>
              {staffLike && a.status === "pending" && <button className="btn sm" onClick={() => act(() => api.patch(`/appointments/${a.id}`, { action: "approve" }), "Visit approved")}>Approve</button>}
              {staffLike && a.status === "approved" && <button className="btn sm" onClick={() => act(() => api.patch(`/appointments/${a.id}`, { action: "complete" }), "Marked completed")}>Complete</button>}
              <button className="btn sm" onClick={() => { setResched(a); setWhen(""); }}>Reschedule</button>
              <button className="btn sm danger" onClick={() => act(() => api.patch(`/appointments/${a.id}`, { action: "cancel" }), "Visit cancelled")}>Cancel</button></>}</td></tr>)}
        </tbody></table></div>
      </State>
      {resched && <Modal title="Reschedule visit" onClose={() => setResched(null)}>
        <Field label="New date and time"><input type="datetime-local" value={when} onChange={(e) => setWhen(e.target.value)} /></Field>
        <button className="btn primary" onClick={async () => (await act(() => api.patch(`/appointments/${resched.id}`, { action: "reschedule", scheduled_at: when }), "Visit rescheduled")) && setResched(null)}>Save</button></Modal>}
    </>
  );
}

export function Rentals() {
  const { user } = useAuth();
  const leases = useFetch(() => api.get("/leases", { params: { per_page: 50 } }), []);
  const [status, setStatus] = useState("");
  const pays = useFetch(() => api.get("/payments", { params: { per_page: 24, status: status || undefined } }), [status]);
  const act = useAct(() => { leases.reload(); pays.reload(); });
  const [rec, setRec] = useState(null);
  const [method, setMethod] = useState({ method: "upi", reference: "" });
  const [open, setOpen] = useState(false);
  const canManage = [...MANAGERS, "owner"].includes(user.role);
  return (
    <>
      <div className="row between wrap gap"><h1>Rentals</h1>{canManage && <button className="btn primary" onClick={() => setOpen(true)}>New lease</button>}</div>
      <h2>Leases</h2>
      <State f={leases} empty={<Empty title="No leases" hint={canManage ? "Create a lease for an available rental property." : "Your landlord will create your lease."} />}>
        <div className="card tablewrap"><table><thead><tr><th>Property</th><th>Tenant</th><th>Term</th><th>Rent</th><th>Deposit</th><th>Status</th><th></th></tr></thead><tbody>
          {leases.data?.map((l) => <tr key={l.id}><td>{l.property_title}</td><td>{l.tenant_name}</td><td>{fdate(l.start_date)} to {fdate(l.end_date)}</td><td>{inr(l.monthly_rent)}</td><td>{inr(l.security_deposit)}</td><td><Chip v={l.status} /></td>
            <td className="row gap">{canManage && l.status === "active" && <><button className="btn sm" onClick={() => act(() => api.post(`/leases/${l.id}/renew`, { months: 12 }), "Lease renewed for 12 months")}>Renew</button><button className="btn sm danger" onClick={() => window.confirm("Terminate this lease?") && act(() => api.post(`/leases/${l.id}/terminate`), "Lease terminated")}>Terminate</button></>}</td></tr>)}
        </tbody></table></div>
      </State>
      <div className="row between wrap gap"><h2>Rent payments</h2><select aria-label="Filter payments" value={status} onChange={(e) => setStatus(e.target.value)}><option value="">All</option><option>pending</option><option>paid</option><option>overdue</option></select></div>
      <p className="muted">These are payments recorded manually by the landlord or manager. No online payment gateway is connected.</p>
      <State f={pays} empty={<Empty title="No payments" />}>
        <div className="card tablewrap"><table><thead><tr><th>Due</th><th>Property</th><th>Tenant</th><th>Amount</th><th>Status</th><th>Paid on</th><th></th></tr></thead><tbody>
          {pays.data?.map((p) => <tr key={p.id}><td>{fdate(p.due_date)}</td><td>{p.property_title}</td><td>{p.tenant_name}</td><td>{inr(p.amount)}</td><td><Chip v={p.status} /></td><td>{fdate(p.paid_date)}{p.method && ` (${p.method})`}</td>
            <td>{canManage && ["pending", "overdue"].includes(p.status) && <button className="btn sm" onClick={() => setRec(p)}>Record payment</button>}</td></tr>)}
        </tbody></table></div>
      </State>
      {rec && <Modal title={`Record payment of ${inr(rec.amount)}`} onClose={() => setRec(null)}>
        <Field label="Method"><select value={method.method} onChange={(e) => setMethod({ ...method, method: e.target.value })}><option value="upi">UPI</option><option value="bank_transfer">Bank transfer</option><option value="cash">Cash</option><option value="cheque">Cheque</option></select></Field>
        <Field label="Reference / receipt no."><input value={method.reference} onChange={(e) => setMethod({ ...method, reference: e.target.value })} /></Field>
        <button className="btn primary" onClick={async () => (await act(() => api.post(`/payments/${rec.id}/record`, method), "Payment recorded")) && setRec(null)}>Record as paid</button></Modal>}
      {open && <LeaseModal onClose={() => setOpen(false)} onDone={() => { setOpen(false); leases.reload(); pays.reload(); }} />}
    </>
  );
}

function LeaseModal({ onClose, onDone }) {
  const toast = useToast();
  const [props, setProps] = useState([]);
  const [tenants, setTenants] = useState([]);
  const [f, setF] = useState({ property_id: "", tenant_id: "", start_date: "", end_date: "", monthly_rent: "", security_deposit: "", due_day: 5 });
  useEffect(() => {
    api.get("/properties", { params: { all: 1, mine: 1, listing_type: "rent", status: "available", approval: "approved", per_page: 100 } }).then((r) => setProps(r.data.data)).catch(() => {});
    api.get("/users/lookup", { params: { role: "tenant" } }).then((r) => setTenants(r.data.data)).catch(() => {});
  }, []);
  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async () => {
    try { await api.post("/leases", { ...f, property_id: Number(f.property_id), tenant_id: Number(f.tenant_id), monthly_rent: f.monthly_rent || undefined }); toast("Lease created and rent schedule generated"); onDone(); } catch (e) { toast(errMsg(e), "err"); }
  };
  return (
    <Modal title="New lease" onClose={onClose}>
      <Field label="Property"><select value={f.property_id} onChange={set("property_id")}><option value="">Select</option>{props.map((p) => <option key={p.id} value={p.id}>{p.title} ({p.city})</option>)}</select></Field>
      <Field label="Tenant"><select value={f.tenant_id} onChange={set("tenant_id")}><option value="">Select</option>{tenants.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></Field>
      <Field label="Start date"><input type="date" value={f.start_date} onChange={set("start_date")} /></Field>
      <Field label="End date"><input type="date" value={f.end_date} onChange={set("end_date")} /></Field>
      <Field label="Monthly rent (₹, blank = listing rent)"><input type="number" value={f.monthly_rent} onChange={set("monthly_rent")} /></Field>
      <Field label="Security deposit (₹)"><input type="number" value={f.security_deposit} onChange={set("security_deposit")} /></Field>
      <Field label="Rent due day (1-28)"><input type="number" min="1" max="28" value={f.due_day} onChange={set("due_day")} /></Field>
      <button className="btn primary" onClick={save}>Create lease</button>
    </Modal>
  );
}

export function Maintenance() {
  const { user } = useAuth();
  const f = useFetch(() => api.get("/maintenance", { params: { per_page: 50 } }), []);
  const act = useAct(f.reload);
  const [form, setForm] = useState({ category: "plumbing", priority: "medium", description: "" });
  const vendors = useFetch(() => (MANAGERS.includes(user.role) ? api.get("/vendors") : Promise.resolve({ data: { data: [] } })), []);
  const upImg = async (m, file) => { if (!file) return; const fd = new FormData(); fd.append("image", file); await act(() => api.post(`/maintenance/${m.id}/image`, fd), "Photo attached"); };
  const isTenant = user.role === "tenant";
  return (
    <>
      <h1>Maintenance</h1>
      {isTenant && <form className="card filters" onSubmit={async (e) => { e.preventDefault(); (await act(() => api.post("/maintenance", form), "Request submitted")) && setForm({ ...form, description: "" }); }}>
        <Field label="Category"><select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{["plumbing", "electrical", "appliance", "structural", "cleaning", "other"].map((c) => <option key={c}>{c}</option>)}</select></Field>
        <Field label="Priority"><select value={form.priority} onChange={(e) => setForm({ ...form, priority: e.target.value })}><option>low</option><option>medium</option><option>high</option></select></Field>
        <Field label="Describe the issue"><input required minLength={5} value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} /></Field>
        <button className="btn primary">Submit request</button></form>}
      <State f={f} empty={<Empty title="No maintenance requests" />}>
        {f.data?.map((m) => <div key={m.id} className="card">
          <div className="row between wrap gap"><div><strong>{m.category}</strong> · {m.property_title}<div className="muted">{m.tenant_name} · {fdt(m.created_at)}</div></div><div className="row gap"><Chip v={m.priority} /><Chip v={m.status} /></div></div>
          <p>{m.description}</p>
          <p className="muted">Assigned to: {m.assigned_to || "not assigned"} · Cost: {inr(m.cost)} {m.cost > 0 && (m.cost_approved ? "(approved by owner)" : "(awaiting owner approval)")}</p>
          {m.has_image && <AuthImg path={`/maintenance/${m.id}/image`} alt="Issue photo" />}
          {isTenant && <Field label="Attach photo (JPG/PNG/WEBP)"><input type="file" accept="image/jpeg,image/png,image/webp" onChange={(e) => upImg(m, e.target.files[0])} /></Field>}
          {MANAGERS.includes(user.role) && <div className="filters">
            <Field label="Vendor"><select value={m.vendor_id || ""} onChange={(e) => e.target.value && act(() => api.patch(`/maintenance/${m.id}`, { vendor_id: Number(e.target.value) }), "Vendor assigned")}><option value="">Select vendor</option>{(vendors.data || []).filter((v) => v.active).map((v) => <option key={v.id} value={v.id}>{v.name} ({v.category})</option>)}</select></Field>
            <Field label="Status"><select value={m.status} onChange={(e) => act(() => api.patch(`/maintenance/${m.id}`, { status: e.target.value }), "Status updated")}>{["open", "assigned", "in_progress", "resolved", "closed"].map((s) => <option key={s}>{s}</option>)}</select></Field>
            <Field label="Assign staff / vendor"><input defaultValue={m.assigned_to || ""} onBlur={(e) => e.target.value !== (m.assigned_to || "") && act(() => api.patch(`/maintenance/${m.id}`, { assigned_to: e.target.value }), "Assigned")} /></Field>
            <Field label="Cost (₹)"><input type="number" min="0" defaultValue={m.cost || ""} onBlur={(e) => e.target.value !== "" && Number(e.target.value) !== m.cost && act(() => api.patch(`/maintenance/${m.id}`, { cost: e.target.value }), "Cost saved")} /></Field></div>}
          {user.role === "owner" && m.cost > 0 && !m.cost_approved && <button className="btn sm primary" onClick={() => act(() => api.patch(`/maintenance/${m.id}`, { cost_approved: true }), "Expense approved")}>Approve expense</button>}
        </div>)}
      </State>
    </>
  );
}

export function Notifications() {
  const f = useFetch(() => api.get("/notifications", { params: { per_page: 50 } }), []);
  const act = useAct(f.reload);
  return (
    <>
      <div className="row between"><h1>Notifications</h1><button className="btn" onClick={() => act(() => api.post("/notifications/read-all"), "All marked as read")}>Mark all read</button></div>
      <State f={f} empty={<Empty title="You're all caught up" />}>
        {f.data?.map((n) => <div key={n.id} className="card row between" style={{ opacity: n.read ? 0.6 : 1 }}>
          <div><strong>{n.title}</strong><div className="muted">{n.body} · {fdt(n.created_at)}</div></div>
          <div className="row gap">{n.link && <Link className="btn sm" to={n.link}>Open</Link>}{!n.read && <button className="btn sm" onClick={() => act(() => api.post(`/notifications/${n.id}/read`))}>Mark read</button>}</div></div>)}
      </State>
    </>
  );
}

export function Favorites() {
  const f = useFetch(() => api.get("/favorites", { params: { per_page: 50 } }), []);
  const act = useAct(f.reload);
  return (
    <>
      <h1>Saved properties</h1>
      <State f={f} empty={<Empty title="No saved properties" hint="Tap the heart on a listing to save it."><Link className="btn primary" to="/">Browse listings</Link></Empty>}>
        <div className="grid g3">{f.data?.map((p) => <PropertyCard key={p.id} p={p} onFav={(x) => act(() => api.post(`/properties/${x.id}/favorite`))} />)}</div>
      </State>
    </>
  );
}
