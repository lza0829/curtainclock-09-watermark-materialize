import { useEffect, useState } from "react";
import { api } from "../api";

export default function Conflicts() {
  const [rows, setRows] = useState([]);
  const [level, setLevel] = useState(null);
  const [err, setErr] = useState("");

  useEffect(() => {
    api
      .conflicts()
      .then((d) => {
        setRows(d.items);
        setLevel(d);
      })
      .catch((e) => setErr(e.message));
  }, []);

  if (err) return <div className="msg err">{err}</div>;

  return (
    <section className="panel">
      <h2>冲突桶</h2>
      {level && (
        <p className="sub">
          冲突计数 {level.conflict_count} · 在途租约 {level.open_leases}
          （与总览同一聚合口径，列表最多展示最近 100 条）
        </p>
      )}
      <table>
        <thead>
          <tr>
            <th>类型</th>
            <th>批窗</th>
            <th>资源</th>
            <th>原因</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 && (
            <tr>
              <td colSpan={5}>暂无冲突</td>
            </tr>
          )}
          {rows.map((r) => (
            <tr key={r.id}>
              <td>{r.kind}</td>
              <td>{r.session_code}</td>
              <td>{r.resource_code}</td>
              <td>{r.reason}</td>
              <td>{r.created_at}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
