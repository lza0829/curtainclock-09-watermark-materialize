# Curtainclock（幕窗钟）

骨架：**批窗定义 → 算力槽/执行器资源依赖就绪 → 开窗租约占用 → 关窗释放与冲突水位互证**

- 前端：http://127.0.0.1:6100 （React + Vite）
- API：http://127.0.0.1:11100

## 本地冒烟（推荐）

```powershell
cd D:\Asolo11\claude-workspace\curtainclock\source
# 本机若无 3.11：py -V:Astral/CPython3.11.15 -m venv .venv
py -V:Astral/CPython3.11.15 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt
$env:PYTHONPATH = "$PWD\backend"
Start-Process .\.venv\Scripts\uvicorn.exe -ArgumentList 'app.main:app','--host','127.0.0.1','--port','11100' -WorkingDirectory "$PWD\backend"
cd frontend
# 前端需 Node ≥18；不足时用 docker compose 起 web
npm install
npm run dev
```

浏览器打开 http://127.0.0.1:6100 ：开一节课 → 同算力槽冲突 → 关窗释放。

## 水位唯一真源

在途租约与冲突计数**不存水位表**，唯一真源是 `leases(status='open')` 与 `conflicts` 两张事实表：

- 读写口径集中在 `backend/app/services/stats.py::water_level()`，每个接口在同一读快照（`db.read_snapshot()`）内聚合，刷新时不会出现半截旧在途。
- 开窗成功只插入租约行，冲突只插入冲突行；写路径不单独改任何计数，因此「只改水位冒充成功」在结构上不可能发生。
- 总览、租约页、冲突页、开窗/关窗响应全部使用同一聚合，页面不再自己 `COUNT` 或改数字。
- 旧库若残留 `watermarks` 表，启动时由 `init_db()` 删除。

冒烟脚本 `_smoke_api.py` 覆盖：开窗 +1 / 关窗 -1 / 冲突加计、写水位表被禁止、手工写假水位不影响展示、列表与总览一致、并发开窗时不出现半截。

## Docker

```powershell
docker compose up -d --build
```
