# Web feature coverage matrix

This matrix distinguishes database/API support from browser UI coverage. Existing desktop features are not automatically browser-complete merely because the Python database method exists.

| Area | API/data layer | Browser UI | Notes |
|---|---|---|---|
| Owner sign-in | Implemented | Implemented | First-owner-only registration; one shared household, not multi-tenant |
| Dashboard | Implemented | Implemented | Live totals and recent activity |
| Inventory CRUD/search/filter | Implemented | Implemented | CSV export in browser |
| Purchases | Create/edit/delete/return methods exposed | Create/list | Edit/delete/returns need full UI controls |
| Household members | Create/update/list | Create/list | Member edit UI pending |
| Shopping lists | Create/items/update/delete/mark purchased/convert | Create/list/add item; create recurring schedule | Item edit/delete/convert and recurring pause/resume controls need UI completion |
| Stores and price history | Implemented | Create/list | Price comparison API exists; richer comparison UI pending |
| Expiry/batches | List/update/consume/waste | List/waste | Batch editing and FIFO consumption controls need UI completion |
| Expenses | Create/update/delete/list | Create/list | Expense edit UI pending |
| Budgets | Create/update/thresholds/list | Create/list | Threshold editor and progress UI pending |
| Reports | Summary and CSV/XLSX/PDF data exports | Summary tables; expense and inventory export controls | Rich interactive charts and broader one-click exports pending |
| Assistant | Uses stored inventory summaries | Basic suggestions | Offline rule-based, not generative AI |
| Notifications | Generate/read/list | List | Read-state UI action pending |
| Settings | Persist selected settings | Basic settings | Full desktop language/theme/backup parity pending |
| Help | N/A | Basic help | Deployment and security guidance included |

## Before a public launch
- Set a unique `AUTH_SECRET` in the backend host.
- Use HTTPS and exact `CORS_ORIGINS`.
- Attach persistent storage for SQLite.
- Do not share the owner password.
- Make a backup before deploying updates.
- For separate households/accounts, implement tenant-scoped PostgreSQL schema and authorization before allowing public account registration.
