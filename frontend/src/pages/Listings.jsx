import { useState } from "react";
import { useParams, useSearchParams, useNavigate } from "react-router-dom";
import { Share2, Heart, Phone } from "lucide-react";
import api, { errMsg } from "../api";
import { useAuth } from "../auth";
import { Reviews } from "./Reviews";
import { useFetch, State, Empty, PropertyCard, Pager, Modal, Field, Img, Chip, inr, useToast } from "../ui";

export function Listings() {
  const [sp, setSp] = useSearchParams();
  const { user } = useAuth();
  const toast = useToast();
  const params = Object.fromEntries(sp);
  const meta = useFetch(() => api.get("/meta"), []);
  const f = useFetch(() => api.get("/properties", { params: { per_page: 12, ...params } }), [sp.toString()]);
  const featured = useFetch(() => api.get("/properties", { params: { featured: 1, per_page: 3 } }), []);
  const set = (k) => (e) => { const n = new URLSearchParams(sp); e.target.value ? n.set(k, e.target.value) : n.delete(k); n.delete("page"); setSp(n); };
  const fav = async (p) => {
    if (!user) return toast("Sign in to save properties", "err");
    try { await api.post(`/properties/${p.id}/favorite`); f.reload(); } catch (e) { toast(errMsg(e), "err"); }
  };
  const M = meta.data || { cities: [], property_types: [] };
  return (
    <>
      <section className="hero"><h1>Find a home, office or plot across India</h1><p>Search verified listings for sale and rent.</p></section>
      <div className="card filters">
        <Field label="Search"><input placeholder="Locality, city, title" defaultValue={params.q} onKeyDown={(e) => e.key === "Enter" && set("q")(e)} onBlur={set("q")} /></Field>
        <Field label="City"><select value={params.city || ""} onChange={set("city")}><option value="">All</option>{M.cities.map((c) => <option key={c}>{c}</option>)}</select></Field>
        <Field label="Type"><select value={params.property_type || ""} onChange={set("property_type")}><option value="">All</option>{M.property_types.map((c) => <option key={c}>{c}</option>)}</select></Field>
        <Field label="Buy or rent"><select value={params.listing_type || ""} onChange={set("listing_type")}><option value="">Any</option><option value="sale">Buy</option><option value="rent">Rent</option></select></Field>
        <Field label="Min price (₹)"><input type="number" min="0" defaultValue={params.min_price} onBlur={set("min_price")} /></Field>
        <Field label="Max price (₹)"><input type="number" min="0" defaultValue={params.max_price} onBlur={set("max_price")} /></Field>
        <Field label="Min bedrooms"><select value={params.bedrooms || ""} onChange={set("bedrooms")}><option value="">Any</option>{[1, 2, 3, 4].map((n) => <option key={n}>{n}</option>)}</select></Field>
        <Field label="Furnishing"><select value={params.furnishing || ""} onChange={set("furnishing")}><option value="">Any</option><option>unfurnished</option><option>semi-furnished</option><option>furnished</option></select></Field>
        <Field label="Sort"><select value={params.sort || "latest"} onChange={set("sort")}><option value="latest">Latest</option><option value="price_asc">Price: low to high</option><option value="price_desc">Price: high to low</option><option value="popular">Most viewed</option></select></Field>
        <button className="btn" onClick={() => setSp({})}>Clear filters</button>
      </div>
      {!sp.toString() && featured.data?.length > 0 && <><h2>Featured</h2><div className="grid g3">{featured.data.map((p) => <PropertyCard key={p.id} p={p} onFav={fav} />)}</div></>}
      <h2>{sp.toString() ? "Results" : "Recently added"}{f.meta && ` (${f.meta.total})`}</h2>
      <State f={f} empty={<Empty title="No properties match" hint="Try removing a filter." />}>
        <div className="grid g3">{f.data?.map((p) => <PropertyCard key={p.id} p={p} onFav={fav} />)}</div>
        <Pager meta={f.meta} onPage={(n) => { const x = new URLSearchParams(sp); x.set("page", n); setSp(x); }} />
      </State>
    </>
  );
}

export function PropertyDetail() {
  const { id } = useParams();
  const { user } = useAuth();
  const nav = useNavigate();
  const toast = useToast();
  const f = useFetch(() => api.get(`/properties/${id}`), [id]);
  const [modal, setModal] = useState(null);
  const [img, setImg] = useState(0);
  const [form, setForm] = useState({ message: "", scheduled_at: "", note: "", amount: "" });
  const p = f.data;

  const need = () => { if (!user) { toast("Please sign in first", "err"); nav("/login"); return false; } return true; };
  const send = async (url, body, msg) => {
    try { await api.post(url, body); toast(msg); setModal(null); } catch (e) { toast(errMsg(e), "err"); }
  };
  const share = async () => {
    const url = window.location.href;
    if (navigator.share) { try { await navigator.share({ title: p.title, url }); } catch { /* cancelled */ } }
    else { await navigator.clipboard.writeText(url); toast("Link copied"); }
  };
  return (
    <State f={f}>
      {p && <>
        <div className="gallery">
          <Img src={(p.images.length ? p.images : [p.cover])[img]} alt={p.title} />
          <div className="side">{(p.images.length > 1 ? p.images : [p.cover, p.cover]).slice(0, 2).map((s, i) => <Img key={i} src={s} alt={p.title} onClick={() => setImg(i)} />)}</div>
        </div>
        <div className="row between wrap gap">
          <div><h1>{p.title}</h1><div className="muted">{p.address}, {p.locality}, {p.city}, {p.state} {p.postal_code}</div></div>
          <div><strong style={{ fontSize: "1.6rem" }}>{p.listing_type === "rent" ? `${inr(p.monthly_rent)}/mo` : inr(p.price)}</strong><div><Chip v={p.status} /> {p.is_demo && <span className="muted">Demo listing</span>}</div></div>
        </div>
        <div className="row gap wrap" style={{ margin: "12px 0" }}>
          <button className="btn primary" onClick={() => need() && setModal("inquiry")}>Contact agent</button>
          <button className="btn" onClick={() => need() && setModal("visit")}>Book a visit</button>
          {p.listing_type === "sale" && p.status === "available" && (!user || user.role === "buyer") && <button className="btn" onClick={() => need() && setModal("offer")}>Make an offer</button>}
          <button className="btn" onClick={async () => { if (!need()) return; try { await api.post(`/properties/${p.id}/favorite`); f.reload(); } catch (e) { toast(errMsg(e), "err"); } }}><Heart size={16} fill={p.is_favorite ? "currentColor" : "none"} /> {p.is_favorite ? "Saved" : "Save"}</button>
          <button className="btn" onClick={share}><Share2 size={16} /> Share</button>
        </div>
        <div className="grid g2">
          <div className="card"><h3>Details</h3>
            <p>{p.description}</p>
            <table><tbody>{[["Type", p.property_type], ["Bedrooms", p.bedrooms], ["Bathrooms", p.bathrooms], ["Balconies", p.balconies], ["Area", `${p.area_sqft} sqft`], ["Furnishing", p.furnishing], ["Parking", p.parking], ["Built", p.year_built]].map(([k, v]) => <tr key={k}><th>{k}</th><td>{v}</td></tr>)}</tbody></table>
          </div>
          <div className="card"><h3>Amenities</h3><div className="row wrap gap">{p.amenities.length ? p.amenities.map((a) => <Chip key={a} v={a} />) : <span className="muted">None listed</span>}</div>
            {p.agent && <><h3>Listing agent</h3><p>{p.agent.name}<br /><span className="muted"><Phone size={14} /> {p.agent.phone || "Use the contact form"}</span></p></>}
          </div>
        </div>
        <Reviews propertyId={p.id} />
        {p.similar.length > 0 && <><h2>Similar properties</h2><div className="grid g3">{p.similar.map((s) => <PropertyCard key={s.id} p={s} />)}</div></>}
        {modal === "inquiry" && <Modal title="Contact agent" onClose={() => setModal(null)}>
          <Field label="Message"><textarea rows={4} value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} /></Field>
          <button className="btn primary" onClick={() => send("/inquiries", { property_id: p.id, message: form.message }, "Inquiry sent")}>Send inquiry</button></Modal>}
        {modal === "offer" && <Modal title="Make an offer" onClose={() => setModal(null)}>
          <p className="muted">Listed at {inr(p.price)}. The seller can accept, reject or counter.</p>
          <Field label="Your offer (₹)"><input type="number" min="1" value={form.amount} onChange={(e) => setForm({ ...form, amount: e.target.value })} /></Field>
          <Field label="Message (optional)"><input value={form.message} onChange={(e) => setForm({ ...form, message: e.target.value })} /></Field>
          <button className="btn primary" onClick={() => send("/offers", { property_id: p.id, amount: Number(form.amount), message: form.message }, "Offer submitted")}>Submit offer</button></Modal>}
        {modal === "visit" && <Modal title="Book a visit" onClose={() => setModal(null)}>
          <Field label="Date and time"><input type="datetime-local" value={form.scheduled_at} onChange={(e) => setForm({ ...form, scheduled_at: e.target.value })} /></Field>
          <Field label="Note (optional)"><input value={form.note} onChange={(e) => setForm({ ...form, note: e.target.value })} /></Field>
          <button className="btn primary" onClick={() => send("/appointments", { property_id: p.id, scheduled_at: form.scheduled_at, note: form.note }, "Visit requested")}>Request visit</button></Modal>}
      </>}
    </State>
  );
}
