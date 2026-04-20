"""Create the 4-company test-bed and exercise the PSQL RLS module.

Runs on module install via ``post_init_hook``. Idempotent where possible —
re-running (via ``odoo -u``) will not duplicate companies, products, or
users (lookups by name / login).
"""

import logging

from odoo import api, SUPERUSER_ID

_logger = logging.getLogger(__name__)


# --- Company specs ---------------------------------------------------------

# Each entry: (company_name, country_xmlid, currency_xmlid, chart_template_xmlid)
# chart_template_xmlid = None means: use existing l10n_ba_fbih_data template
# (looked up by name because its xmlid prefix depends on the installed module).
COMPANY_SPECS = [
    ("CompanySL-1", "base.si", "base.EUR", "bringout_l10n_si_demo.chart_template_si_demo"),
    ("CompanyHR-1", "base.hr", "base.EUR", "bringout_l10n_hr_demo.chart_template_hr_demo"),
    ("CompanyHR-2", "base.hr", "base.EUR", "bringout_l10n_hr_demo.chart_template_hr_demo"),
    ("CompanyBA-1", "base.ba", "base.BAM", None),
]

BA_CHART_NAME_HINT = "FBiH"  # substring match against account.chart.template.name

SHARED_PRODUCTS = ["Product 01", "Product 02"]

# Demo users — login, name, allowed-company-names, lock-company-name-or-None
DEMO_USERS = [
    # Per-country payroll clerks — all locked via psql_company_lock_id.
    # These are the users that exercise the RLS module.
    {
        "login": "demo.payroll.ba@hodi.ba",
        "name": "Demo Payroll Clerk (Bosnia)",
        "allowed_companies": ["CompanyBA-1"],
        "default_company": "CompanyBA-1",
        "psql_lock": "CompanyBA-1",
        "groups": ["hr.group_hr_user"],
    },
    {
        "login": "demo.payroll.hr@hodi.ba",
        "name": "Demo Payroll Clerk (Croatia)",
        "allowed_companies": ["CompanyHR-1"],
        "default_company": "CompanyHR-1",
        "psql_lock": "CompanyHR-1",
        "groups": ["hr.group_hr_user"],
    },
    {
        "login": "demo.payroll.si@hodi.ba",
        "name": "Demo Payroll Clerk (Slovenia)",
        "allowed_companies": ["CompanySL-1"],
        "default_company": "CompanySL-1",
        "psql_lock": "CompanySL-1",
        "groups": ["hr.group_hr_user"],
    },
    # Unlocked users — normal multi-company access, no RLS enforcement.
    {
        "login": "demo.manager.hr@hodi.ba",
        "name": "Demo HR Manager (Croatia)",
        "allowed_companies": ["CompanyHR-1", "CompanyHR-2"],
        "default_company": "CompanyHR-1",
        "psql_lock": None,
        "groups": ["hr.group_hr_manager"],
    },
    {
        "login": "demo.group.admin@hodi.ba",
        "name": "Demo Group Admin",
        "allowed_companies": ["CompanySL-1", "CompanyHR-1", "CompanyHR-2", "CompanyBA-1"],
        "default_company": "CompanyBA-1",
        "psql_lock": None,
        "groups": ["base.group_system"],
    },
]

DEMO_PASSWORD = "demo1234"  # dev only


# Demo employees per company — populates hr_employee so the RLS filter
# has something visible to filter. Also exercises hr_contract / hr_leave
# downstream when those modules are installed.
DEMO_EMPLOYEES = {
    "CompanySL-1": [
        ("Janez Novak",      "janez.novak@example.si",      "Direktor"),
        ("Ana Kovač",        "ana.kovac@example.si",         "Računovođa"),
    ],
    "CompanyHR-1": [
        ("Ivan Horvat",      "ivan.horvat@example.hr",       "Direktor"),
        ("Marija Kovačić",   "marija.kovacic@example.hr",    "Prodaja"),
    ],
    "CompanyHR-2": [
        ("Tomislav Babić",   "tomislav.babic@example.hr",    "Direktor"),
        ("Petra Marić",      "petra.maric@example.hr",       "Logistika"),
    ],
    "CompanyBA-1": [
        ("Emir Hodžić",      "emir.hodzic@example.ba",       "Direktor"),
        ("Amina Bašić",      "amina.basic@example.ba",       "Računovodstvo"),
        ("Mirza Delić",      "mirza.delic@example.ba",       "Prodaja"),
    ],
}


# --- Helpers ---------------------------------------------------------------


def _ensure_company(env, name, country_xmlid, currency_xmlid):
    company = env["res.company"].search([("name", "=", name)], limit=1)
    if company:
        return company
    vals = {
        "name": name,
        "country_id": env.ref(country_xmlid).id,
        "currency_id": env.ref(currency_xmlid).id,
    }
    _logger.info("multi_company_example: creating company %s", name)
    return env["res.company"].create(vals)


def _resolve_ba_chart_template(env):
    tmpl = env["account.chart.template"].search(
        [("name", "ilike", BA_CHART_NAME_HINT)], limit=1
    )
    if not tmpl:
        _logger.warning(
            "multi_company_example: no l10n_ba FBiH chart.template found; "
            "CompanyBA-1 will not have a CoA loaded. Install l10n_ba_fbih_data."
        )
    return tmpl


def _load_chart(env, company, template):
    if not template:
        return
    # Skip if company already has accounts (idempotency).
    existing = env["account.account"].search_count(
        [("company_id", "=", company.id)]
    )
    if existing:
        _logger.info(
            "multi_company_example: %s already has %d accounts; skipping CoA load",
            company.name, existing,
        )
        return
    _logger.info(
        "multi_company_example: loading chart %s onto %s",
        template.name, company.name,
    )
    # try_loading is the public method in Odoo 16 that installs the template
    # onto the given company.
    template.with_company(company).try_loading(company=company, install_demo=False)


def _ensure_shared_products(env):
    product_obj = env["product.product"]
    for name in SHARED_PRODUCTS:
        existing = product_obj.search([("name", "=", name)], limit=1)
        if existing:
            continue
        _logger.info("multi_company_example: creating shared product %s", name)
        product_obj.create({
            "name": name,
            "type": "consu",
            "sale_ok": True,
            "purchase_ok": True,
            "company_id": False,  # shared across all companies
            "list_price": 100.0,
        })


def _ensure_user(env, spec, companies_by_name):
    user = env["res.users"].search([("login", "=", spec["login"])], limit=1)
    allowed = env["res.company"].browse([
        companies_by_name[n].id for n in spec["allowed_companies"]
    ])
    default_company = companies_by_name[spec["default_company"]]
    groups = env["res.groups"]
    for xmlid in spec["groups"]:
        groups |= env.ref(xmlid)

    # Assign payroll access + stack marker groups together.
    # The stack marker alone isn't enough: payroll menu children require the
    # real access group (payroll.group_payroll_user / ba_payroll.group_payroll_user).
    # Odoo auto-hides a parent menu when every child is hidden, so without the
    # access group the whole tree disappears for the user even though the stack
    # marker is satisfied on the root.
    #
    #   locked to BA           -> BA stack marker + ba_payroll.group_payroll_user
    #   locked to HR/SL        -> OCA stack marker + payroll.group_payroll_user
    #   unlocked (admin, mgr)  -> both stacks + both access groups
    stack_ba = env.ref(
        "multi_company_example_ba_hr_si_data.group_payroll_stack_ba",
        raise_if_not_found=False,
    )
    stack_oca = env.ref(
        "multi_company_example_ba_hr_si_data.group_payroll_stack_oca",
        raise_if_not_found=False,
    )
    access_ba = env.ref("ba_payroll.group_payroll_user", raise_if_not_found=False)
    access_oca = env.ref("payroll.group_payroll_user", raise_if_not_found=False)
    if stack_ba and stack_oca:
        lock_name = spec.get("psql_lock")
        if lock_name == "CompanyBA-1":
            groups |= stack_ba
            if access_ba:
                groups |= access_ba
        elif lock_name in ("CompanyHR-1", "CompanyHR-2", "CompanySL-1"):
            groups |= stack_oca
            if access_oca:
                groups |= access_oca
        else:
            # unlocked user — grant both stacks + both access groups
            groups |= stack_ba | stack_oca
            if access_ba:
                groups |= access_ba
            if access_oca:
                groups |= access_oca

    if not user:
        _logger.info("multi_company_example: creating user %s", spec["login"])
        user = env["res.users"].create({
            "login": spec["login"],
            "name": spec["name"],
            "password": DEMO_PASSWORD,
            "company_id": default_company.id,
            "company_ids": [(6, 0, allowed.ids)],
            "groups_id": [(6, 0, groups.ids)],
        })
    else:
        user.write({
            "name": spec["name"],
            "company_id": default_company.id,
            "company_ids": [(6, 0, allowed.ids)],
            "groups_id": [(4, g.id) for g in groups],
        })

    # Wire PSQL lock if the field exists (module is a hard dependency so it
    # should — but check defensively).
    if "psql_company_lock_id" in user._fields:
        lock_name = spec["psql_lock"]
        lock = companies_by_name[lock_name] if lock_name else env["res.company"]
        user.psql_company_lock_id = lock.id if lock else False
    return user


def _ensure_demo_employees(env, companies_by_name):
    """Create demo employees per company. Idempotent: matches by
    (name, company_id). Skips silently if the `hr` module isn't loaded
    yet — which shouldn't happen since this module depends on hr.
    """
    employee_obj = env["hr.employee"]
    for company_name, roster in DEMO_EMPLOYEES.items():
        company = companies_by_name.get(company_name)
        if not company:
            _logger.warning(
                "multi_company_example: company %s not found; "
                "skipping employee creation", company_name,
            )
            continue
        for name, work_email, job_title in roster:
            existing = employee_obj.search([
                ("name", "=", name),
                ("company_id", "=", company.id),
            ], limit=1)
            if existing:
                continue
            _logger.info(
                "multi_company_example: creating employee %s at %s",
                name, company_name,
            )
            employee_obj.create({
                "name": name,
                "work_email": work_email,
                "job_title": job_title,
                "company_id": company.id,
            })


# --- Entry points ----------------------------------------------------------


def post_init_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # 1. Companies.
    companies_by_name = {}
    for name, country_xmlid, currency_xmlid, chart_xmlid in COMPANY_SPECS:
        companies_by_name[name] = _ensure_company(env, name, country_xmlid, currency_xmlid)

    # 2. Charts per company.
    for name, _country, _currency, chart_xmlid in COMPANY_SPECS:
        company = companies_by_name[name]
        if chart_xmlid:
            template = env.ref(chart_xmlid, raise_if_not_found=False)
        else:
            template = _resolve_ba_chart_template(env)
        _load_chart(env, company, template)

    # 3. Shared products.
    _ensure_shared_products(env)

    # 4. Demo users with PSQL lock on the Bosnia payroll clerk.
    for spec in DEMO_USERS:
        _ensure_user(env, spec, companies_by_name)

    # 5. Demo employees per company (gives the RLS filter something
    #    visible to filter — otherwise all hr_employee lists are empty).
    _ensure_demo_employees(env, companies_by_name)

    _logger.info("multi_company_example: setup complete")


def uninstall_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Demo users — remove.
    logins = [s["login"] for s in DEMO_USERS]
    users = env["res.users"].search([("login", "in", logins)])
    if users:
        _logger.info("multi_company_example: removing %d demo users", len(users))
        users.unlink()

    # Shared products — remove only if untouched by transactions.
    products = env["product.product"].search([("name", "in", SHARED_PRODUCTS)])
    for p in products:
        try:
            p.unlink()
        except Exception:
            _logger.info(
                "multi_company_example: cannot remove product %s (has refs); archiving",
                p.name,
            )
            p.active = False

    # Companies — archive rather than delete (Odoo forbids deletion once
    # accounting transactions exist; even if clean, a removed company can
    # break hundreds of FKs on a shared install).
    names = [s[0] for s in COMPANY_SPECS]
    companies = env["res.company"].search([("name", "in", names)])
    for c in companies:
        try:
            c.active = False
        except Exception:
            _logger.exception(
                "multi_company_example: failed to archive company %s", c.name
            )
    _logger.info("multi_company_example: uninstall hook done")
