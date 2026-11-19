import { useEffect, useState } from "react";
import api, { download, errMsg } from "../api";
import { useAuth } from "../auth";
import { useFetch, State, Empty, Chip, Modal, Field, fdate, fdt, useToast } from "../ui";

const CATS = ["property", "ownership", "rental_agreement", "sale_agreement", "tenant", "invoice", "other"];

export function Documents() {
  const { user } = useAuth();
  const toast = useToast();
  const [cat, setCat] = useState("");
  const [expiring, setExpiring] = useState(false);
  const f = useFetch(() => api.get("/documents", { params: { category: cat || undefined, expiring: expiring ? 1 : undefined } }), [cat, expiring]);
  const [props, setProps] = useState([]);
  const [form, setForm] = useState({ title: "", category: "property", property_id: "", visibility: "private", expires_on: "" });
  const [file, setFile] = useState(null);
  const [log, setLog] = useState(null);
  useEffect(() => { api.get("/properties", { params: { per_page: 100, ...(["owner"].includes(user.role) ? { mine: 1 } : ["buyer", "tenant"].includes(user.role) ? {} : { all: 1 }) } }).then((r) => setProps(r.data.data)).catch(() => {}); }, [user.role]);
  const upload = async (e) => {
    e.preventDefault();
    if (!file) return toast("Choose a file", "err");
    const fd = new FormData();
    fd.append("file", file);
    Object.entries(form).forEach(([k, v]) => v && fd.append(k, v));
    try { await api.post("/documents", fd); toast("Document uploaded"); setFile(null); e.target.reset(); setForm({ ...form, title: "" }); f.reload(); } catch (er) { toast(errMsg(er), "err"); }
  };
  const del = async (d) => { if (!window.confirm("Delete this document?")) return; try { await api.delete(`/documents/${d.id}`); toast("Deleted"); f.reload(); } catch (e) { toast(errMsg(e), "err"); } };
  const showLog = async (d) => { try { const r = await api.get(`/documents/${d.id}/activity`); setLog({ d, rows: r.data.data }); } catch (e) { toast(errMsg(e), "err"); } };
  return (
    <>
      <h1>Documents</h1>
      <form className="card filters" onSubmit={upload}>
        <Field label="Title"><input required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
        <Field label="Category"><select value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })}>{CATS.map((c) => <option key={c} value={c}>{c.replace("_", " ")}</option>)}</select></Field>
        <Field label="Property (optional)"><select value={form.property_id} onChange={(e) => setForm({ ...form, property_id: e.target.value })}><option value="">None</option>{props.map((p) => <option key={p.id} value={p.id}>{p.title}</option>)}</select></Field>
        <Field label="Who can view"><select value={form.visibility} onChange={(e) => setForm({ ...form, visibility: e.target.value })}><option value="private">Only me and managers</option><option value="parties">Parties of the property</option></select></Field>
        <Field label="Expiry date"><input type="date" value={form.expires_on} onChange={(e) => setForm({ ...form, expires_on: e.target.value })} /></Field>
        <Field label="File (PDF, PNG, JPG, DOCX, 5 MB)"><input type="file" accept=".pdf,.png,.jpg,.jpeg,.docx" onChange={(e) => setFile(e.target.files[0])} /></Field>
        <button className="btn primary">Upload</button>
      </form>
      <div className="row gap wrap" style={{ marginBottom: 12 }}>
        <select aria-label="Category filter" value={cat} onChange={(e) => setCat(e.target.value)}><option value="">All categories</option>{CATS.map((c) => <option key={c} value={c}>{c.replace("_", " ")}</option>)}</select>
        <label className="row gap"><input type="checkbox" style={{ width: "auto" }} checked={expiring} onChange={(e) => setExpiring(e.target.checked)} /> Expiring within 30 days</label>
      </div>
      <State f={f} empty={<Empty title="No documents" hint="Upload agreements, ownership papers or invoices." />}>
        <div className="card tablewrap"><table><thead><tr><th>Title</th><th>Category</th><th>Property</th><th>Uploaded by</th><th>Expires</th><th></th></tr></thead><tbody>
          {f.data?.map((d) => <tr key={d.id}><td>{d.title}{d.is_demo && " (demo)"}</td><td>{d.category.replace("_", " ")}</td><td>{d.property_title || "-"}</td><td>{d.uploaded_by}</td><td>{d.expires_on ? <>{fdate(d.expires_on)} {d.expired && <Chip v="overdue" />}</> : "-"}</td>
            <td className="row gap wrap"><button className="btn sm" onClick={() => download(`/documents/${d.id}/download`, d.original_name).catch((e) => toast(errMsg(e), "err"))}>Download</button><button className="btn sm" onClick={() => showLog(d)}>History</button><button className="btn sm danger" onClick={() => del(d)}>Delete</button></td></tr>)}
        </tbody></table></div>
      </State>
      {log && <Modal title={`History: ${log.d.title}`} onClose={() => setLog(null)}>{log.rows.map((r, i) => <p key={i} className="muted">{fdt(r.at)} · {r.user} · {r.action}</p>)}</Modal>}
    </>
  );
}
