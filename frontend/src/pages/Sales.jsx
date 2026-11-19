import { useState } from "react";
import { Link } from "react-router-dom";
import api, { errMsg } from "../api";
import { useAuth, MANAGERS, STAFF } from "../auth";
import { useFetch, State, Empty, Chip, Pager, Modal, Field, inr, fdate, fdt, useToast } from "../ui";

function useAct(reload) {
  const toast = useToast();
  return async (fn, msg) => { try { await fn(); toast(msg); reload(); return true; } catch (e) { toast(errMsg(e), "err"); return false; } };
}

export function Offers() {
  const { user } = useAuth();
  const [page, setPage] = useState(1);
  const f = useFetch(() => api.get("/offers", { params: { page, per_page: 10 } }), [page]);
  const act = useAct(f.reload);
  const [counter, setCounter] = useState(null);
  const [amt, setAmt] = useState("");
  const seller = [...STAFF, "owner"].includes(user.role);
  const patch = (o, body, msg) => act(() => api.patch(`/offers/${o.id}`, body), msg);
  return (
    <>
      <h1>Offers</h1>
      <State f={f} empty={<Empty title="No offers yet" hint="Buyers can make offers from any sale listing." />}>
        <div className="card tablewrap"><table><thead><tr><th>Property</th><th>Buyer</th><th>Listed</th><th>Offer</th><th>Counter</th><th>Status</th><th>Date</th><th></th></tr></thead><tbody>
          {f.data?.map((o) => <tr key={o.id}><td><Link to={`/properties/${o.property_id}`}>{o.property_title}</Link></td><td>{o.buyer_name}</td><td>{inr(o.listed_price)}</td><td>{inr(o.amount)}</td><td>{o.counter_amount ? inr(o.counter_amount) : "-"}</td><td><Chip v={o.status} /></td><td>{fdt(o.created_at)}</td>
            <td className="row gap wrap">
              {seller && o.status === "pending" && <><button className="btn sm" onClick={() => patch(o, { action: "accept" }, "Offer accepted, deal created")}>Accept</button><button className="btn sm" onClick={() => { setCounter(o); setAmt(""); }}>Counter</button><button className="btn sm danger" onClick={() => patch(o, { action: "reject" }, "Offer rejected")}>Reject</button></>}
              {user.role === "buyer" && o.status === "countered" && <button className="btn sm primary" onClick={() => patch(o, { action: "accept_counter" }, "Counter accepted, deal created")}>Accept counter</button>}
              {user.role === "buyer" && ["pending", "countered"].includes(o.status) && <button className="btn sm danger" onClick={() => patch(o, { action: "withdraw" }, "Offer withdrawn")}>Withdraw</button>}</td></tr>)}
        </tbody></table></div>
        <Pager meta={f.meta} onPage={setPage} />
      </State>
      {counter && <Modal title="Counter-offer" onClose={() => setCounter(null)}>
        <Field label={`Your counter (₹) to ${inr(counter.amount)}`}><input type="number" value={amt} onChange={(e) => setAmt(e.target.value)} /></Field>
        <button className="btn primary" onClick={async () => (await patch(counter, { action: "counter", counter_amount: Number(amt) }, "Counter-offer sent")) && setCounter(null)}>Send counter</button></Modal>}
    </>
  );
}

export function Deals() {
  const { user } = useAuth();
  const f = useFetch(() => api.get("/deals", { params: { per_page: 20 } }), []);
  const comm = useFetch(() => (MANAGERS.includes(user.role) || user.role === "agent" ? api.get("/commissions", { params: { per_page: 50 } }) : Promise.resolve({ data: { data: [] } })), []);
  const reload = () => { f.reload(); comm.reload(); };
  const act = useAct(reload);
  const [modal, setModal] = useState(null);
  const [v, setV] = useState({});
  const seller = [...STAFF, "owner"].includes(user.role);
  const post = (d, a, extra = {}, msg) => act(() => api.patch(`/deals/${d.id}`, { action: a, ...extra }), msg);
  return (
    <>
      <h1>Sales deals</h1>
      <p className="muted">Amounts are manually recorded; no online payment gateway is connected.</p>
      <State f={f} empty={<Empty title="No deals yet" hint="A deal is created when an offer is accepted." />}>
        {f.data?.map((d) => <div className="card" key={d.id}>
          <div className="row between wrap gap"><div><strong><Link to={`/properties/${d.property_id}`}>{d.property_title}</Link></strong><div className="muted">Buyer: {d.buyer_name} · Price {inr(d.price)} · Commission {d.commission_rate}%{d.is_demo && " · demo"}</div></div><Chip v={d.status} /></div>
          <progress value={d.paid_total} max={d.price} style={{ width: "100%", margin: "8px 0" }} />
          <div className="muted">Recorded {inr(d.paid_total)} · Balance {inr(d.balance)} · Booking {inr(d.booking_amount)}{d.agreement_date && ` · Agreement ${fdate(d.agreement_date)}`}</div>
          <table><tbody>{d.milestones.map((m) => <tr key={m.id}><td>{m.title}</td><td>{inr(m.amount)}</td><td>{fdate(m.due_date)}</td><td><Chip v={m.status} /></td><td>{seller && m.status === "pending" && !["completed", "cancelled"].includes(d.status) && <button className="btn sm" onClick={() => act(() => api.post(`/milestones/${m.id}/pay`), "Milestone recorded as paid")}>Record paid</button>}</td></tr>)}</tbody></table>
          {seller && !["completed", "cancelled"].includes(d.status) && <div className="row gap wrap" style={{ marginTop: 8 }}>
            <button className="btn sm" onClick={() => { setModal({ t: "booking", d }); setV({ amount: d.booking_amount || "" }); }}>Record booking amount</button>
            <button className="btn sm" onClick={() => { setModal({ t: "milestone", d }); setV({}); }}>Add milestone</button>
            {d.status === "booked" && <button className="btn sm" onClick={() => post(d, "agreement", {}, "Sale agreement recorded")}>Record agreement</button>}
            <button className="btn sm primary" onClick={() => window.confirm("Complete the sale? The property will be marked sold and commission calculated.") && post(d, "complete", {}, "Deal completed")}>Complete deal</button>
            <button className="btn sm danger" onClick={() => window.confirm("Cancel this deal?") && post(d, "cancel", {}, "Deal cancelled")}>Cancel</button></div>}
        </div>)}
      </State>
      {(MANAGERS.includes(user.role) || user.role === "agent") && <><h2>Commissions</h2>
        <State f={comm} empty={<Empty title="No commissions yet" hint="Commission is created when a deal is completed." />}>
          <div className="card tablewrap"><table><thead><tr><th>Property</th><th>Agent</th><th>Rate</th><th>Amount</th><th>Status</th><th></th></tr></thead><tbody>
            {comm.data?.map((c) => <tr key={c.id}><td>{c.property_title}</td><td>{c.agent_name}</td><td>{c.rate}%</td><td>{inr(c.amount)}</td><td><Chip v={c.status} /></td><td>{MANAGERS.includes(user.role) && c.status === "pending" && <button className="btn sm" onClick={() => act(() => api.post(`/commissions/${c.id}/pay`), "Commission marked paid")}>Mark paid</button>}</td></tr>)}
          </tbody></table></div></State></>}
      {modal?.t === "booking" && <Modal title="Booking amount" onClose={() => setModal(null)}>
        <Field label="Amount (₹)"><input type="number" value={v.amount} onChange={(e) => setV({ amount: e.target.value })} /></Field>
        <button className="btn primary" onClick={async () => (await post(modal.d, "record_booking", { amount: Number(v.amount) }, "Booking recorded")) && setModal(null)}>Save</button></Modal>}
      {modal?.t === "milestone" && <Modal title="Add payment milestone" onClose={() => setModal(null)}>
        <Field label="Title"><input value={v.title || ""} onChange={(e) => setV({ ...v, title: e.target.value })} /></Field>
        <Field label="Amount (₹)"><input type="number" value={v.amount || ""} onChange={(e) => setV({ ...v, amount: e.target.value })} /></Field>
        <Field label="Due date"><input type="date" value={v.due_date || ""} onChange={(e) => setV({ ...v, due_date: e.target.value })} /></Field>
        <button className="btn primary" onClick={async () => (await act(() => api.post(`/deals/${modal.d.id}/milestones`, { ...v, amount: Number(v.amount) }), "Milestone added")) && setModal(null)}>Add</button></Modal>}
    </>
  );
}
