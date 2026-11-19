import { Link } from "react-router-dom";
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid } from "recharts";
import api from "../api";
import { useAuth, ROLE_LABEL } from "../auth";
import { useFetch, State, Chip, inr, fdate, fdt } from "../ui";

const Stat = ({ label, value }) => <div className="card stat"><div className="muted">{label}</div><div className="n">{value ?? 0}</div></div>;

function Revenue({ data, title = "Rent recorded per month" }) {
  return <div className="card"><h3>{title}</h3><div style={{ height: 240 }}><ResponsiveContainer><BarChart data={data}><CartesianGrid strokeDasharray="3 3" stroke="var(--line)" /><XAxis dataKey="month" /><YAxis tickFormatter={(v) => (v >= 1e5 ? `${v / 1e5}L` : v)} /><Tooltip formatter={(v) => inr(v)} /><Bar dataKey="revenue" fill="var(--brass)" radius={[4, 4, 0, 0]} /></BarChart></ResponsiveContainer></div></div>;
}

export default function Dashboard() {
  const { user } = useAuth();
  const f = useFetch(() => api.get("/dashboard"), []);
  const d = f.data;
  return (
    <>
      <h1>Welcome, {user.name}</h1><p className="muted">{ROLE_LABEL[user.role]} dashboard · figures are live from the database (demo data until you add your own)</p>
      <State f={f}>{d && <>
        {d.kind === "admin" && <>
          <div className="grid g4"><Stat label="Users" value={d.total_users} /><Stat label="Properties" value={d.total_properties} /><Stat label="Active listings" value={d.active_listings} /><Stat label="Sold" value={d.sold} /><Stat label="Rented" value={d.rented} /><Stat label="Rent recorded" value={inr(d.rental_revenue)} /><Stat label="Overdue rent" value={inr(d.overdue_rent)} /><Stat label="Pending approvals" value={d.pending_approvals} /><Stat label="Open maintenance" value={d.open_maintenance} /></div>
          <div className="grid g2"><Revenue data={d.monthly} />
            <div className="card"><h3>Recent activity</h3>{d.recent_activity.length ? d.recent_activity.map((a) => <p key={a.id} className="muted"><b>{a.user || "System"}</b> {a.action} {a.entity || ""} · {fdt(a.created_at)}</p>) : <p className="muted">No activity yet.</p>}</div></div>
        </>}
        {d.kind === "agent" && <>
          <div className="grid g4"><Stat label="Assigned properties" value={d.assigned_properties} /><Stat label="Active listings" value={d.active_listings} /><Stat label="Inquiries" value={d.inquiries} /><Stat label="New inquiries" value={d.new_inquiries} /><Stat label="Converted" value={d.converted} /><Stat label="Upcoming visits" value={d.upcoming_visits} /><Stat label="Deals closed" value={d.deals_closed} /><Stat label="Sales value" value={inr(d.sales_value)} /><Stat label="Commission earned" value={inr(d.commission_total)} /><Stat label="Commission pending" value={inr(d.commission_pending)} /></div>
          <div className="grid g2"><div className="card"><h3>Pipeline</h3>{d.pipeline.map((x) => <p key={x.name}><Chip v={x.name} /> {x.count}</p>)}</div>
            <div className="card"><h3>Follow-ups this week</h3>{d.follow_ups.length ? d.follow_ups.map((i) => <p key={i.id}>{i.name} · {i.property_title} · <span className="muted">{fdate(i.follow_up_date)}</span></p>) : <p className="muted">No follow-ups due.</p>}</div></div>
        </>}
        {d.kind === "owner" && <>
          <div className="grid g4"><Stat label="Owned properties" value={d.owned_properties} /><Stat label="Occupied" value={d.occupied} /><Stat label="Rental income" value={inr(d.rental_income)} /><Stat label="Pending rent" value={inr(d.pending_rent)} /><Stat label="Open maintenance" value={d.open_maintenance} /></div>
          <div className="grid g2"><Revenue data={d.monthly} /><div className="card"><h3>Active leases</h3>{d.leases.length ? d.leases.map((l) => <p key={l.id}>{l.property_title} · {l.tenant_name}<br /><span className="muted">{fdate(l.start_date)} to {fdate(l.end_date)} · {inr(l.monthly_rent)}/mo</span></p>) : <p className="muted">No active leases.</p>}</div></div>
        </>}
        {d.kind === "tenant" && <>
          {d.lease ? <div className="grid g4"><Stat label="Property" value={d.lease.property_title} /><Stat label="Monthly rent" value={inr(d.lease.monthly_rent)} /><Stat label="Next due" value={d.next_due ? fdate(d.next_due.due_date) : "-"} /><Stat label="Open requests" value={d.open_maintenance} /></div> : <div className="empty"><strong>No active lease</strong><p>Ask your agent or landlord to create one.</p></div>}
          <div className="card"><h3>Payment history <Link className="btn sm" to="/rentals">Details</Link></h3><div className="tablewrap"><table><thead><tr><th>Due</th><th>Amount</th><th>Status</th><th>Paid on</th></tr></thead><tbody>{d.payments.map((p) => <tr key={p.id}><td>{fdate(p.due_date)}</td><td>{inr(p.amount)}</td><td><Chip v={p.status} /></td><td>{fdate(p.paid_date)}</td></tr>)}</tbody></table></div><p className="muted">Payments are manually recorded receipts, not online transactions.</p></div>
        </>}
        {d.kind === "buyer" && <><div className="grid g4"><Stat label="Saved properties" value={d.saved} /><Stat label="Inquiries" value={d.inquiries} /><Stat label="Scheduled visits" value={d.visits} /></div><div className="card"><h3>Purchase progress</h3>{d.deals.length ? d.deals.map((x) => <div key={x.id}><strong>{x.property_title}</strong> <Chip v={x.status} /><div className="muted">Paid {inr(x.paid_total)} of {inr(x.price)}</div><progress value={x.paid_total} max={x.price} style={{ width: "100%" }} /></div>) : <p className="muted">No purchases in progress. Make an offer on a sale listing.</p>}</div></>}
      </>}</State>
    </>
  );
}
