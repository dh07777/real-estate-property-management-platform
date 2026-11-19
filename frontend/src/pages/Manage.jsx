import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import api, { errMsg } from "../api";
import { useAuth, MANAGERS, STAFF } from "../auth";
import { useFetch, State, Empty, Chip, Pager, Field, inr, useToast } from "../ui";

export function ManageList() {
  const { user } = useAuth();
  const toast = useToast();
  const [page, setPage] = useState(1);
  const [approval, setApproval] = useState("");
  const f = useFetch(() => api.get("/properties", { params: { [STAFF.includes(user.role) ? "all" : "mine"]: 1, per_page: 10, page, approval: approval || undefined } }), [page, approval]);
  const act = async (fn, msg) => { try { await fn(); toast(msg); f.reload(); } catch (e) { toast(errMsg(e), "err"); } };
  const isMgr = MANAGERS.includes(user.role);
  return (
    <>
      <div className="row between wrap gap"><h1>Properties</h1><div className="row gap">
        <select aria-label="Filter approval" value={approval} onChange={(e) => { setApproval(e.target.value); setPage(1); }}><option value="">All approvals</option><option>pending</option><option>approved</option><option>rejected</option></select>
        <Link className="btn primary" to="/manage/new">Add property</Link></div></div>
      <State f={f} empty={<Empty title="No properties yet" hint="Add your first listing."><Link className="btn primary" to="/manage/new">Add property</Link></Empty>}>
        <div className="card tablewrap"><table><thead><tr><th>Title</th><th>City</th><th>Listing</th><th>Price</th><th>Status</th><th>Approval</th><th></th></tr></thead><tbody>
          {f.data?.map((p) => <tr key={p.id}><td><Link to={`/properties/${p.id}`}>{p.title}</Link>{p.featured && " ★"}</td><td>{p.city}</td><td>{p.listing_type}</td><td>{inr(p.listing_type === "rent" ? p.monthly_rent : p.price)}</td><td><Chip v={p.status} /></td><td><Chip v={p.approval} /></td>
            <td className="row gap wrap"><Link className="btn sm" to={`/manage/${p.id}`}>Edit</Link>
              {isMgr && p.approval !== "approved" && <button className="btn sm" onClick={() => act(() => api.post(`/properties/${p.id}/review`, { decision: "approved" }), "Approved")}>Approve</button>}
              {isMgr && p.approval === "pending" && <button className="btn sm danger" onClick={() => act(() => api.post(`/properties/${p.id}/review`, { decision: "rejected" }), "Rejected")}>Reject</button>}
              {isMgr && <button className="btn sm" onClick={() => act(() => api.post(`/properties/${p.id}/feature`), "Featured updated")}>{p.featured ? "Unfeature" : "Feature"}</button>}
              {p.status !== "archived" && <button className="btn sm danger" onClick={() => window.confirm("Archive this property?") && act(() => api.delete(`/properties/${p.id}`), "Archived")}>Archive</button>}</td></tr>)}
        </tbody></table></div>
        <Pager meta={f.meta} onPage={setPage} />
      </State>
    </>
  );
}

const EMPTY = { title: "", description: "", property_type: "apartment", listing_type: "sale", price: "", monthly_rent: "", address: "", city: "", state: "", postal_code: "", locality: "", bedrooms: 2, bathrooms: 2, balconies: 1, area_sqft: "", furnishing: "unfurnished", parking: 1, year_built: 2020, amenities: "", owner_id: "", agent_id: "" };

export function PropertyForm() {
  const { id } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const [f, setF] = useState(EMPTY);
  const [owners, setOwners] = useState([]);
  const [agents, setAgents] = useState([]);
  const [images, setImages] = useState([]);
  const [errs, setErrs] = useState({});
  const isMgr = MANAGERS.includes(user.role);

  useEffect(() => {
    if (STAFF.includes(user.role)) api.get("/users/lookup", { params: { role: "owner" } }).then((r) => setOwners(r.data.data)).catch(() => {});
    if (isMgr) api.get("/users/lookup", { params: { role: "agent" } }).then((r) => setAgents(r.data.data)).catch(() => {});
    if (id) api.get(`/properties/${id}`).then((r) => { const p = r.data.data; setImages(p.images); setF({ ...EMPTY, ...Object.fromEntries(Object.entries(p).map(([k, v]) => [k, v ?? ""])), amenities: p.amenities.join(", "), owner_id: p.owner_id || "", agent_id: p.agent?.id || "" }); }).catch((e) => toast(errMsg(e), "err"));
    // eslint-disable-next-line
  }, [id]);

  const set = (k) => (e) => setF({ ...f, [k]: e.target.value });
  const save = async (e) => {
    e.preventDefault();
    setErrs({});
    const body = { ...f, amenities: f.amenities.split(",").map((s) => s.trim()).filter(Boolean), owner_id: f.owner_id || undefined, agent_id: f.agent_id || undefined };
    try {
      const r = id ? await api.put(`/properties/${id}`, body) : await api.post("/properties", body);
      toast(id ? "Property updated" : "Property created");
      nav(id ? "/manage" : `/manage/${r.data.data.id}`);
    } catch (er) { setErrs(er.response?.data?.errors || {}); toast(errMsg(er), "err"); }
  };
  const upload = async (e) => {
    const file = e.target.files[0];
    if (!file) return;
    const fd = new FormData();
    fd.append("image", file);
    try { const r = await api.post(`/properties/${id}/images`, fd); setImages([...images, r.data.data.url]); toast("Image uploaded"); } catch (er) { toast(errMsg(er), "err"); }
  };
  const T = (k, label, type = "text", extra = {}) => <Field label={label}><input type={type} value={f[k]} onChange={set(k)} {...extra} />{errs[k] && <small style={{ color: "var(--bad)" }}>{errs[k]}</small>}</Field>;
  return (
    <form className="card" onSubmit={save}>
      <h1>{id ? "Edit property" : "Add property"}</h1>
      {user.role === "owner" && <p className="muted">New and edited listings are reviewed by an admin before going public.</p>}
      <div className="filters">
        {T("title", "Title", "text", { required: true })}
        <Field label="Type"><select value={f.property_type} onChange={set("property_type")}>{["apartment", "villa", "house", "commercial", "land", "office"].map((t) => <option key={t}>{t}</option>)}</select></Field>
        <Field label="Listing"><select value={f.listing_type} onChange={set("listing_type")}><option value="sale">Sale</option><option value="rent">Rent</option></select></Field>
        {f.listing_type === "sale" ? T("price", "Price (₹)", "number", { min: 0 }) : T("monthly_rent", "Monthly rent (₹)", "number", { min: 0 })}
        {T("address", "Address")}{T("locality", "Locality")}{T("city", "City", "text", { required: true })}{T("state", "State")}{T("postal_code", "Postal code")}
        {T("bedrooms", "Bedrooms", "number", { min: 0 })}{T("bathrooms", "Bathrooms", "number", { min: 0 })}{T("balconies", "Balconies", "number", { min: 0 })}
        {T("area_sqft", "Area (sq ft)", "number", { min: 1 })}{T("parking", "Parking slots", "number", { min: 0 })}{T("year_built", "Year built", "number")}
        <Field label="Furnishing"><select value={f.furnishing} onChange={set("furnishing")}><option>unfurnished</option><option>semi-furnished</option><option>furnished</option></select></Field>
        {STAFF.includes(user.role) && <Field label="Owner"><select value={f.owner_id} onChange={set("owner_id")}><option value="">Select</option>{owners.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></Field>}
        {isMgr && <Field label="Assigned agent"><select value={f.agent_id} onChange={set("agent_id")}><option value="">Unassigned</option>{agents.map((o) => <option key={o.id} value={o.id}>{o.name}</option>)}</select></Field>}
      </div>
      <Field label="Amenities (comma separated)"><input value={f.amenities} onChange={set("amenities")} placeholder="Lift, Gym, Power Backup" /></Field>
      <Field label="Description"><textarea rows={4} value={f.description} onChange={set("description")} /></Field>
      <div className="row gap" style={{ marginTop: 12 }}><button className="btn primary">Save property</button><button type="button" className="btn" onClick={() => nav("/manage")}>Cancel</button></div>
      {id ? <div style={{ marginTop: 20 }}><h3>Photos</h3><div className="row wrap gap">{images.map((s) => <img key={s} src={s} alt="" width="120" style={{ borderRadius: 8 }} />)}</div><Field label="Upload image (JPG, PNG, WEBP up to 5 MB)"><input type="file" accept="image/jpeg,image/png,image/webp" onChange={upload} /></Field></div> : <p className="muted">Save the property first, then add photos.</p>}
    </form>
  );
}
