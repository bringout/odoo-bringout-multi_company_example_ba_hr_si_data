# multi_company_example_ba_hr_si_data

Multi-company test bed — a representative demo for multi-company features
in bring.out Odoo 16, with particular focus on exercising
`odoo-bringout-multi_company_protect_psql_payroll`.

## What gets created on install

### 4 companies

| Company         | Country           | Currency | CoA template                |
| --------------- | ----------------- | -------- | --------------------------- |
| CompanySL-1     | Slovenia          | EUR      | `chart_template_si_demo`    |
| CompanyHR-1     | Croatia           | EUR      | `chart_template_hr_demo`    |
| CompanyHR-2     | Croatia           | EUR      | `chart_template_hr_demo`    |
| CompanyBA-1     | Bosnia & Herceg.  | BAM      | `l10n_ba_fbih_data` CoA     |

### 2 shared products

`Product 01` and `Product 02` — visible to **all** companies (they have no
`company_id` set, which is how Odoo declares records shared across the
whole database).

### Demo users (exercise the RLS module)

| Login                          | Role                         | Notes                                        |
| ------------------------------ | ---------------------------- | -------------------------------------------- |
| `demo.payroll.ba@hodi.ba`      | Bosnia payroll clerk         | **Locked** to CompanyBA-1 via `psql_company_lock_id` — exercises PSQL RLS |
| `demo.manager.hr@hodi.ba`      | Multi-company HR manager     | Allowed on both Croatian companies           |
| `demo.group.admin@hodi.ba`     | Group admin                  | Allowed on all 4 companies, no PSQL lock     |

All demo users get the password `demo1234` (dev only — change in real
deployments).

## Dependencies

* `odoo-bringout-l10n_si_demo` — Slovenia demo CoA + DDV
* `odoo-bringout-l10n_hr_demo` — Croatia demo CoA + PDV
* `odoo-bringout-l10n_ba` — Bosnia base (cities, country states)
* `odoo-bringout-l10n_ba_data` — Bosnia common accounting data
* `odoo-bringout-l10n_ba` (`l10n_ba_fbih_data` module) — FBiH CoA
* `odoo-bringout-multi_company_protect_psql_payroll` — PSQL RLS layer

## Install

```
Apps → "Multi-Company Example BA/HR/SI (test bed)" → Install
```

On install, the `post_init_hook`:
1. Creates the 4 companies.
2. Loads the respective CoA template onto each company.
3. Creates the 2 shared products.
4. Creates the 3 demo users, wires up allowed_companies, and sets
   `psql_company_lock_id` on the Bosnia payroll clerk.

## Manual test plan for the RLS module

1. Log in as `demo.payroll.ba@hodi.ba` (Bosnia payroll clerk).
2. Open HR → Employees. You should see **only CompanyBA-1** employees
   (even if you try to switch companies in the switcher).
3. Try via XML-RPC or a URL-forced company_id parameter — PostgreSQL RLS
   denies the row at SQL level.
4. Log in as `demo.group.admin@hodi.ba` — no lock, full access to all
   4 companies as normal.

## Uninstall

Uninstalling removes the demo users and products, and archives the 4
companies (Odoo prevents deleting companies with transactions).

## License

AGPL-3
