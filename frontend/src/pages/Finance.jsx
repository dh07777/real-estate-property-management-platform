import { useEffect, useState } from "react";
import { BarChart, Bar, XAxis, YAxis, Tooltip, Legend, ResponsiveContainer, CartesianGrid } from "recharts";
import api, { download, errMsg } from "../api";
import { useAuth, MANAGERS } from "../auth";
import { useFetch, State, Empty, Chip, Pager, Modal, Field, inr, fdate, useToast } from "../ui";

const EXP = ["tax", "utilities", "insurance", "repairs", "marketing", "management_fee", "other"];

export default function Finance() {
  const { user } = useAuth();
  const toast = useToast();
  const [range, setRange] = useState({ from: "", to: "" });
  const [page, setPage] = useState(1);
  const params = { from: range.from || undefined, to: range.to || undefined };
  const s = useFetch(() => api.get("/finance/summary", { params }), [range.from, range.to]);
  const led = useFetch(() => api.get("/finance/ledger", { params: { ...params, page } }), [range.from, range.to, page]);
  const ma = useFetch(() => api.get("/maintenance/analytics"), []);
  const [open, setOpen] = useState(false);
  const [props, setProps] = useState([]);
  const [f, setF] = useState({ property_id: "", category: "tax", amount: "", spent_on: "", description: "" });
  useEffect(() => { api.get("/properties", { params: { per_page: 100, ...(user.role === "owner" ? { mine: 1 } : { all: 1 }) } }).then((r) => setProps(r.data.data)).catch(() => {}); }, [user.role]);
  const save = async () => {
    try { await api.post("/expenses", { ...f, property_id: f.property_id ? Number(f.property_id) : undefined, amount: Number(f.amount) }); toast("Expense recorded"); setOpen(false); s.reload(); led.reload(); } catch (e) { toast(errMsg(e), "err"); }
  };
  const d = s.data;
  return (
    <>
      <div className="row between wrap gap"><h1>Finance</h1><div className="row gap wrap">
        <Field label="From"><input type="date" value={range.from} onChange={(e) => { setRange({ ...range, from: e.target.value }); setPage(1); }} /></Field>
        <Field label="To"><input type="date" value={range.to} onChange={(e) => { setRange({ ...range, to: e.target.value }); setPage(1); }} /></Field>
        <button className="btn primary" onClick={() => setOpen(true)}>Add expense</button>
        {MANAGERS.includes(user.role) && <><button className="btn" onClick={() => download("/reports/ledger?format=xlsx", "ledger.xlsx")}>Excel</button><button className="btn" onClick={() => download("/reports/ledger?format=pdf", "ledger.pdf")}>PDF</button></>}</div></div>
      <State f={s}>{d && <>
        <div className="grid g4">{[["Income (recorded)", d.income], ["Expenses", d.expense], ["Net", d.net], ["Outstanding rent", d.outstanding_rent], ["Deposits held", d.security_deposits_held]].map(([l, v]) => <div key={l} className="card stat"><div className="muted">{l}</div><div className="n">{inr(v)}</div></div>)}</div>
        <p className="muted">{d.note}</p>
        <div className="grid g2">
          <div className="card"><h3>Monthly income vs expense</h3>{d.monthly.length ? <div style={{ height: 250 }}><ResponsiveContainer><BarChart data={d.monthly}><CartesianGrid strokeDasharray="3 3" stroke="var(--line)" /><XAxis dataKey="month" /><YAxis tickFormatter={(v) => (v >= 1e5 ? `${v / 1e5}L` : v)} /><Tooltip formatter={(v) => inr(v)} /><Legend /><Bar dataKey="income" fill="var(--ok)" /><Bar dataKey="expense" fill="var(--bad)" /></BarChart></ResponsiveContainer></div> : <p className="muted">No entries in this range.</p>}</div>
          <div className="card"><h3>Expenses by category</h3>{d.by_category.length ? d.by_category.map((c) => <p key={c.category} className="row between"><span>{c.category}</span><strong>{inr(c.amount)}</strong></p>) : <p className="muted">None</p>}
            <h3>Property-wise revenue</h3>{d.by_property.length ? d.by_property.map((c) => <p key={c.property} className="row between"><span>{c.property}</span><strong>{inr(c.income)}</strong></p>) : <p className="muted">None</p>}</div>
        </div></>}</State>
      <h2>Maintenance analytics</h2>
      <State f={ma} empty={<Empty title="No maintenance data" />}>{ma.data && <div className="grid g2">
        <div className="card"><h3>By category</h3>{ma.data.by_category.map((c) => <p key={c.category} className="row between"><span>{c.category} ({c.count})</span><strong>{inr(c.cost)}</strong></p>)}</div>
        <div className="card"><h3>By status</h3>{ma.data.by_status.map((c) => <p key={c.status}><Chip v={c.status} /> {c.count}</p>)}</div></div>}</State>
      <h2>Transaction history</h2>
      <State f={led} empty={<Empty title="No transactions in this range" />}>
        <div className="card tablewrap"><table><thead><tr><th>Date</th><th>Type</th><th>Category</th><th>Property</th><th>Amount</th><th>Reference</th></tr></thead><tbody>
          {led.data?.map((e, i) => <tr key={i}><td>{fdate(e.date)}</td><td><Chip v={e.type === "income" ? "paid" : e.type === "expense" ? "overdue" : "pending"} /> {e.type}</td><td>{e.category}</td><td>{e.property}</td><td>{inr(e.amount)}</td><td>{e.reference}</td></tr>)}</tbody></table></div>
        <Pager meta={led.meta} onPage={setPage} />
      </State>
      {open && <Modal title="Record expense" onClose={() => setOpen(false)}>
        <Field label="Property"><select value={f.property_id} onChange={(e) => setF({ ...f, property_id: e.target.value })}><option value="">{user.role === "owner" ? "Select" : "General (no property)"}</option>{props.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></Field>
        <Field label="Category"><select value={f.category} onChange={(e) => setF({ ...f, category: e.target.value })}>{EXP.map((c) => <option key={c}>{c}</option>)}</select></Field>
        <Field label="Amount (₹)"><input type="number" value={f.amount} onChange={(e) => setF({ ...f, amount: e.target.value })} /></Field>
        <Field label="Date"><input type="date" value={f.spent_on} onChange={(e) => setF({ ...f, spent_on: e.target.value })} /></Field>
        <Field label="Description"><input value={f.description} onChange={(e) => setF({ ...f, description: e.target.value })} /></Field>
        <button className="btn primary" onClick={save}>Save expense</button></Modal>}
    </>
  );
}
