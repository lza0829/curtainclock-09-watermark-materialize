import { useEffect, useState } from "react";
import { api } from "../api";

function fmtMin(m) {
  const h = String(Math.floor(m / 60)).padStart(2, "0");
  const mm = String(m % 60).padStart(2, "0");
  return `${h}:${mm}`;
}

export default function Leases() {
  const [rows, setRows] = useState([]);
  const [level, setLevel] = useState(null);
  const [msg, setMsg] = useState("");
  const [err, setErr] = useState("");

  async function load() {
    // items 与水位来自后端同一快照，页面不再自己数行。
    const d = await api.leases();
    setRows(d.items);
    setLevel(d);
  }

  useEffect(() => {
    load().catch((e) => setErr(e.message));
  }, []);

  async function closeOne(lease_no) {
    setMsg("");
    setErr("");
    try {
      const r = await api.closeLease(lease_no);
      setMsg(`已关窗释放 ${r.lease_no}；在途租约 ${r.open_leases}`);
      await load();
    } catch (e) {
      setErr(e.message);
      await load().catch(() => {});
    }
  }

  return (
    <section className="panel">
      <h2>租约</h2>
      {level && (
        <p className="sub">
          在途租约 {level.open_leases} · 冲突 {level.conflict_count}
          （与总览同一聚合口径）
        </p>
      )}
      {msg && <div className="msg">{msg}</div>}
      {err && <div className="msg err">{err}</div>}
      <table>
        <thead>
          <tr>
            <th>租约号</th>
            <th>批窗</th>
            <th>资源</th>
            <th>时段</th>
            <th>状态</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          {rows.map((r) => (
            <tr key={r.lease_no}>
              <td>{r.lease_no}</td>
              <td>{r.session_code}</td>
              <td>
                {r.room_code} / {r.teacher_code}
              </td>
              <td>
                {r.day} {fmtMin(r.start_min)}–{fmtMin(r.end_min)}
              </td>
              <td>{r.status === "open" ? "占用中" : "已释放"}</td>
              <td>
                <button
                  className="secondary"
                  disabled={r.status !== "open"}
                  onClick={() => closeOne(r.lease_no)}
                >
                  关窗释放
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
