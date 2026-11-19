import { useState } from "react";
import api, { download } from "../api";
import { useAuth, ROLE_LABEL } from "../auth";
import { useFetch, State, Empty, Chip, Pager, fdt, useToast } from "../ui";
import { errMsg } from "../api";

export function Users() {
  const { user } = useAuth();
  const toast = useToast();
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const f = useFetch(() => api.get("/admin/users", { params: { q: q || undefined, page, per_page: 15 } }), [q, page]);
  const patch = async (u, body, msg) => { try { await api.patch(`/admin/users/${u.id}`, body); toast(msg); f.reload(); } catch (e) { toast(errMsg(e), "err"); } };
  return (
    <>
      <div className="row between wrap gap"><h1>Users</h1><input style={{ maxWidth: 260 }} placeholder="Search name or email" onChange={(e) => { setQ(e.target.value); setPage(1); }} /></div>
      <State f={f} empty={<Empty title="No users found" />}>
        <div className="card tablewrap"><table><thead><tr><th>Name</th><th>Email</th><th>Role</th><th>Status</th><th></th></tr></thead><tbody>
          {f.data?.map((u) => <tr key={u.id}><td>{u.name}{u.is_demo && " (demo)"}</td><td>{u.email}</td>
            <td>{user.role === "super_admin" && u.id !== user.id ? <select value={u.role} onChange={(e) => patch(u, { role: e.target.value }, "Role updated")}>{Object.entries(ROLE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select> : ROLE_LABEL[u.role]}</td>
            <td><Chip v={u.active ? "active" : "suspended"} /></td>
            <td>{u.id !== user.id && <button className="btn sm" onClick={() => patch(u, { active: !u.active }, u.active ? "Account suspended" : "Account activated")}>{u.active ? "Suspend" : "Activate"}</button>}</td></tr>)}
        </tbody></table></div>
        <Pager meta={f.meta} onPage={setPage} />
      </State>
    </>
  );
}

export function AuditLogs() {
  const [page, setPage] = useState(1);
  const f = useFetch(() => api.get("/admin/audit-logs", { params: { page, per_page: 20 } }), [page]);
  return (
    <>
      <h1>Audit log</h1><p className="muted">Sign-ins and administrative actions. Passwords and secrets are never stored here.</p>
      <State f={f} empty={<Empty title="No activity yet" />}>
        <div className="card tablewrap"><table><thead><tr><th>When</th><th>User</th><th>Action</th><th>Entity</th><th>Detail</th></tr></thead><tbody>
          {f.data?.map((a) => <tr key={a.id}><td>{fdt(a.created_at)}</td><td>{a.user || "-"}</td><td>{a.action}</td><td>{a.entity} {a.entity_id}</td><td>{a.detail}</td></tr>)}
        </tbody></table></div>
        <Pager meta={f.meta} onPage={setPage} />
      </State>
    </>
  );
}

const REPORTS = [["inventory", "Property inventory"], ["rentals", "Rental agreements"], ["payments", "Rent payments"], ["maintenance", "Maintenance"], ["leads", "Leads"], ["deals", "Sales deals"], ["commissions", "Commissions"], ["ledger", "Financial ledger (12 months)"], ["occupancy", "Rental occupancy"], ["lease_expiry", "Lease expiry (90 days)"], ["appointments", "Appointments"]];

export function Reports() {
  const toast = useToast();
  const [name, setName] = useState("inventory");
  const f = useFetch(() => api.get(`/reports/${name}`), [name]);
  const dl = async (fmt) => { try { await download(`/reports/${name}?format=${fmt}`, `${name}.${fmt}`); } catch (e) { toast(errMsg(e), "err"); } };
  return (
    <>
      <div className="row between wrap gap"><h1>Reports</h1><div className="row gap">
        <select aria-label="Report" value={name} onChange={(e) => setName(e.target.value)}>{REPORTS.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select>
        <button className="btn" onClick={() => dl("xlsx")}>Export Excel</button><button className="btn" onClick={() => dl("pdf")}>Export PDF</button></div></div>
      <State f={{ ...f, data: f.data?.rows }} empty={<Empty title="No records for this report" />}>
        <div className="card tablewrap"><table><thead><tr>{f.data?.columns.map((c) => <th key={c}>{c}</th>)}</tr></thead><tbody>
          {f.data?.rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j}>{String(c)}</td>)}</tr>)}
        </tbody></table></div>
      </State>
    </>
  );
}
