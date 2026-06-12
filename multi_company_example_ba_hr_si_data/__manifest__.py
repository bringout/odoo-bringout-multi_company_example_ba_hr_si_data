{
    "name": "Multi-Company Example BA/HR/SI (test bed)",
    "summary": "Demo multi-company setup: 4 companies (BA/HR×2/SI) + shared products + ba_payroll side-by-side with EE payroll stubs",
    "description": """
Multi-Company Example — Bosnia / Croatia / Slovenia (Odoo 19)
============================================================

Representative test bed for multi-company features in bring.out Odoo 19,
whose v19-specific purpose is to prove that **ba_payroll** (the `ba.*`
namespaced OCA-payroll fork) installs and runs **side by side with the
Odoo Enterprise `hr_payroll` model stack** on a stock Community Edition
instance — without an Enterprise license.

The Enterprise stack is supplied by the **non-functional CE stubs** of
`odoo-bringout-dummy-payroll-ee` (`hr_payroll` → `hr_holidays_gantt` →
`hr_gantt` → `web_gantt`), which reproduce the Enterprise models/fields
in the `hr.*` namespace with no business logic. Because ba_payroll lives
entirely in `ba.*`, the two stacks share no model names and coexist in
one database (see
https://www.hodi.ba/blog/payroll-i-ba-payroll-side-by-side-2026.md/).

On install creates:
* 4 companies: CompanySL-1, CompanyHR-1, CompanyHR-2, CompanyBA-1
* BA FBiH chart of accounts on CompanyBA-1 (l10n_ba_fbih_data). SI/HR
  demo CoA is skipped on v19 — the bringout_l10n_si_demo /
  bringout_l10n_hr_demo modules are not yet ported past 16.0; the hook
  creates those companies without a CoA (defensive: logs + skips).
* 2 shared products (Product 01, Product 02) with per-company pricelists
* demo users — payroll clerks locked per company (Bosnia / Croatia /
  Slovenia) via psql_company_lock_id, an HR manager across the Croatian
  entities, and a group admin across all
* payroll "stack marker" groups that gate which payroll menu tree each
  clerk sees: BA clerk → ba_payroll menus; HR/SI clerk → EE hr_payroll
  (stub) menus; admin → both

NOTE: this 19.0 branch is the structural scaffold. ba_payroll carries
v16-derived code stamped 19.0 (OCA payroll core is not yet ported to 19),
so runtime fixups (CoA-loading API, ORM/JS deltas) land here as the
side-by-side test is actually exercised on a live v19 instance.

See README for the manual test plan that exercises the PostgreSQL RLS
protection on the locked user.
    """,
    "version": "19.0.1.0.0",
    "author": "bring.out doo Sarajevo",
    "website": "https://www.bring.out.ba",
    "category": "Localization",
    "license": "AGPL-3",
    "depends": [
        "base",
        "account",
        "hr",
        "product",
        # BA FBiH chart of accounts (has a 19.0 branch). SI/HR demo CoA
        # modules (bringout_l10n_si_demo / bringout_l10n_hr_demo) are
        # 16.0-only and intentionally NOT depended on here — the hook
        # creates the HR/SI companies without a CoA until those modules
        # are ported.
        "l10n_ba_fbih_data",
        # ── Enterprise payroll stack — non-functional CE stubs ──────────
        # odoo-bringout-dummy-payroll-ee. The whole chain is listed so the
        # example pins the EXACT Enterprise dependency graph (hr_payroll
        # declares hr_holidays_gantt → hr_gantt → web_gantt). These provide
        # the `hr.*` payroll models that ba_payroll is tested against.
        "hr_payroll",
        "hr_holidays_gantt",
        "hr_gantt",
        "web_gantt",
        # ── BA payroll stack — generated OCA fork, ba.* namespace ────────
        "ba_payroll",
        # NOTE: multi_company_protect_psql_payroll is deliberately NOT in
        # depends. The example module only *uses* psql_company_lock_id
        # defensively (guarded by an `if "..." in user._fields` check).
        # This lets you install/uninstall the RLS module independently to
        # observe example behavior with vs. without PSQL protection.
    ],
    "data": [
        "security/payroll_stack_groups.xml",
    ],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
