{
    "name": "Multi-Company Example BA/HR/SI (test bed)",
    "summary": "Demo multi-company setup: 4 companies (BA/HR×2/SI) + shared products + payroll clerk RLS example",
    "description": """
Multi-Company Example — Bosnia / Croatia / Slovenia
===================================================

Representative test bed for multi-company features in bring.out Odoo 16,
with particular focus on exercising the
`multi_company_protect_psql_payroll` module.

On install creates:
* 4 companies: CompanySL-1, CompanyHR-1, CompanyHR-2, CompanyBA-1
* Appropriate CoA per company (SI demo / HR demo / BA FBiH)
* 2 shared products (Product 01, Product 02)
* 3 demo users — payroll clerk locked to Bosnia, HR manager across
  Croatian entities, group admin across all

See README for the manual test plan that exercises the PostgreSQL RLS
protection on the locked user.
    """,
    "version": "16.0.1.2.0",
    "author": "bring.out doo Sarajevo",
    "website": "https://www.bring.out.ba",
    "category": "Localization",
    "license": "AGPL-3",
    "depends": [
        "base",
        "account",
        "hr",
        "product",
        "bringout_l10n_si_demo",
        "bringout_l10n_hr_demo",
        "l10n_ba_fbih_data",
        "multi_company_protect_psql_payroll",
    ],
    "data": [],
    "post_init_hook": "post_init_hook",
    "uninstall_hook": "uninstall_hook",
    "installable": True,
    "application": False,
    "auto_install": False,
}
