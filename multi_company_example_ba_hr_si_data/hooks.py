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

# Per-country VAT rate on the sale side. Used both to wire the correct
# account.tax onto the shared products' taxes_id (so SO lines pick up the
# right VAT when the order runs under a given company) and to pick the
# tax amount when creating the pricelist items below.
SALE_VAT_RATE = {
    "CompanyBA-1": 17.0,  # PDV 17%
    "CompanyHR-1": 25.0,  # HR PDV 25%
    "CompanyHR-2": 25.0,
    "CompanySL-1": 22.0,  # SI DDV 22%
}

# Per-company list price (ex-VAT) for each shared product, in the
# company's own currency. User-specified illustrative conversion:
# "if in Croatia it's 100 EUR, in Bosnia it's 170 KM" — not the official
# 1 EUR = 1.95583 BAM peg, but a round, readable demo ratio.
PRODUCT_PRICES = {
    "Product 01": {
        "CompanyBA-1": 170.0,  # BAM
        "CompanyHR-1": 100.0,  # EUR
        "CompanyHR-2": 100.0,
        "CompanySL-1": 105.0,  # EUR — slightly higher than Croatia by user choice
    },
    "Product 02": {
        "CompanyBA-1": 340.0,
        "CompanyHR-1": 200.0,
        "CompanyHR-2": 200.0,
        "CompanySL-1": 210.0,
    },
}

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


# Demo customers — one per country. Each row carries country-appropriate
# tax/registry numbers so the sale and invoicing flows that read these
# fields (e.g. Bosnian fiscalization, Croatian OIB validation) have
# non-empty plausible data to work with.
#   BA: company_registry = JIB (13 digits), vat = ID PDV (12 digits)
#   HR: OIB (11 digits) serves as both; vat carries the "HR" prefix
#   SI: matična številka (7 digits) as registry; vat = "SI" + 8 digits
DEMO_CUSTOMERS = [
    {
        "company_name": "CompanyBA-1",
        "name": "Test Bosnia Kupac",
        "country_xmlid": "base.ba",
        "vat": "123456789012",
        "company_registry": "1234567890123",
    },
    {
        "company_name": "CompanyHR-1",
        "name": "Test Croatia Kupac",
        "country_xmlid": "base.hr",
        "vat": "HR12345678901",
        "company_registry": "12345678901",
    },
    {
        "company_name": "CompanySL-1",
        "name": "Test Slovenia Kupac",
        "country_xmlid": "base.si",
        "vat": "SI12345678",
        "company_registry": "1234567",
    },
]


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


def _find_sale_tax(env, company, rate):
    """Locate the sale-side VAT tax at ``rate`` percent for ``company``.

    HR / SI chart templates instantiate per-company taxes automatically;
    BA's l10n_ba_data defines plain ``account.tax`` records (no
    ``account.tax.template``) which end up owned by whichever company
    was active at install time (typically the main company). When no
    tax exists on the target company, this function copies a matching
    record into it so SO lines running under that company have the
    expected rate available.
    """
    tax = env["account.tax"].search([
        ("company_id", "=", company.id),
        ("type_tax_use", "=", "sale"),
        ("amount", "=", rate),
        ("amount_type", "=", "percent"),
    ], limit=1)
    if tax:
        return tax
    template = env["account.tax"].search([
        ("type_tax_use", "=", "sale"),
        ("amount", "=", rate),
        ("amount_type", "=", "percent"),
    ], limit=1)
    if not template:
        return tax  # empty recordset
    _logger.info(
        "multi_company_example: no %.1f%% sale tax on %s — copying from %s",
        rate, company.name, template.company_id.name or "<global>",
    )
    return env["account.tax"].create({
        "name": template.name,
        "description": template.description,
        "amount": template.amount,
        "amount_type": template.amount_type,
        "type_tax_use": template.type_tax_use,
        "country_id": template.country_id.id,
        "company_id": company.id,
    })


def _ensure_shared_products(env, companies_by_name):
    product_obj = env["product.product"]
    # Gather sale-side VAT for every company that has a rate declared.
    taxes = env["account.tax"]
    for company_name, rate in SALE_VAT_RATE.items():
        company = companies_by_name.get(company_name)
        if not company:
            continue
        tax = _find_sale_tax(env, company, rate)
        if not tax:
            _logger.warning(
                "multi_company_example: no %.1f%% sale tax found for %s — "
                "CoA may not be loaded yet; shared-product tax wiring skipped",
                rate, company_name,
            )
            continue
        taxes |= tax
    for name in SHARED_PRODUCTS:
        existing = product_obj.search([("name", "=", name)], limit=1)
        if existing:
            # Refresh taxes on an already-created product so upgrades
            # pick up new companies / new tax rules without losing the
            # rest of the record.
            if taxes:
                existing.write({"taxes_id": [(6, 0, taxes.ids)]})
            continue
        _logger.info("multi_company_example: creating shared product %s", name)
        vals = {
            "name": name,
            "type": "consu",
            "sale_ok": True,
            "purchase_ok": True,
            "company_id": False,  # shared across all companies
            "list_price": 100.0,   # overridden per company by pricelists
        }
        if taxes:
            vals["taxes_id"] = [(6, 0, taxes.ids)]
        product_obj.create(vals)


def _ensure_pricelists(env, companies_by_name):
    """One pricelist per company, priced in the company's own currency.

    Each pricelist carries fixed-price items for every shared product
    mapped in PRODUCT_PRICES. The company's currency is authoritative —
    we don't attempt conversion. Idempotent: matches pricelists by
    (name, company_id), and pricelist items by (pricelist, product).
    """
    pricelist_obj = env["product.pricelist"]
    item_obj = env["product.pricelist.item"]
    product_obj = env["product.product"]
    results = {}
    for company_name, company in companies_by_name.items():
        pl_name = f"Pricelist {company_name}"
        pl = pricelist_obj.search([
            ("name", "=", pl_name),
            ("company_id", "=", company.id),
        ], limit=1)
        if not pl:
            _logger.info(
                "multi_company_example: creating pricelist %s (%s)",
                pl_name, company.currency_id.name,
            )
            pl = pricelist_obj.create({
                "name": pl_name,
                "currency_id": company.currency_id.id,
                "company_id": company.id,
            })
        results[company_name] = pl
        for product_name, by_company in PRODUCT_PRICES.items():
            price = by_company.get(company_name)
            if price is None:
                continue
            product = product_obj.search([
                ("name", "=", product_name),
            ], limit=1)
            if not product:
                continue
            existing_item = item_obj.search([
                ("pricelist_id", "=", pl.id),
                ("product_tmpl_id", "=", product.product_tmpl_id.id),
            ], limit=1)
            item_vals = {
                "pricelist_id": pl.id,
                "applied_on": "1_product",
                "product_tmpl_id": product.product_tmpl_id.id,
                "compute_price": "fixed",
                "fixed_price": price,
            }
            if existing_item:
                existing_item.write({
                    "compute_price": "fixed",
                    "fixed_price": price,
                })
            else:
                item_obj.create(item_vals)
    return results


def _assign_pricelists_to_customers(env, companies_by_name, pricelists_by_company):
    """Wire each demo customer's ``property_product_pricelist`` to its
    company's pricelist, so creating a sale order for Test X Kupac picks
    the right currency + price without manual selection.

    Note: ``property_product_pricelist`` is company-dependent; we set it
    under the target company's context so the value lands on the right
    company slice of ir.property.
    """
    partner_obj = env["res.partner"]
    for spec in DEMO_CUSTOMERS:
        company = companies_by_name.get(spec["company_name"])
        if not company:
            continue
        pl = pricelists_by_company.get(spec["company_name"])
        if not pl:
            continue
        partner = partner_obj.search([
            ("name", "=", spec["name"]),
            ("company_id", "=", company.id),
        ], limit=1)
        if not partner:
            continue
        partner.with_company(company).write({
            "property_product_pricelist": pl.id,
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


def _ensure_demo_customers(env, companies_by_name):
    """Create one test customer per country. Idempotent: matches by
    (name, company_id). VAT / company_registry values are test fixtures,
    not real entity numbers.
    """
    partner_obj = env["res.partner"]
    for spec in DEMO_CUSTOMERS:
        company = companies_by_name.get(spec["company_name"])
        if not company:
            _logger.warning(
                "multi_company_example: company %s not found; "
                "skipping customer %s", spec["company_name"], spec["name"],
            )
            continue
        existing = partner_obj.search([
            ("name", "=", spec["name"]),
            ("company_id", "=", company.id),
        ], limit=1)
        if existing:
            continue
        _logger.info(
            "multi_company_example: creating customer %s at %s",
            spec["name"], spec["company_name"],
        )
        partner_obj.create({
            "name": spec["name"],
            "country_id": env.ref(spec["country_xmlid"]).id,
            "vat": spec["vat"],
            "company_registry": spec["company_registry"],
            "company_id": company.id,
            "customer_rank": 1,
            "is_company": True,
        })


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

    # 3. Shared products — with per-country sale VAT wired onto taxes_id.
    _ensure_shared_products(env, companies_by_name)

    # 4. Demo users with PSQL lock on the Bosnia payroll clerk.
    for spec in DEMO_USERS:
        _ensure_user(env, spec, companies_by_name)

    # 5. Demo employees per company (gives the RLS filter something
    #    visible to filter — otherwise all hr_employee lists are empty).
    _ensure_demo_employees(env, companies_by_name)

    # 6. Demo customers per company (one per country, with local tax /
    #    registry numbers for use in sale / invoice flows).
    _ensure_demo_customers(env, companies_by_name)

    # 7. Per-company pricelists + customer pricelist assignment.
    pricelists_by_company = _ensure_pricelists(env, companies_by_name)
    _assign_pricelists_to_customers(env, companies_by_name, pricelists_by_company)

    _logger.info("multi_company_example: setup complete")


def uninstall_hook(cr, registry):
    env = api.Environment(cr, SUPERUSER_ID, {})

    # Demo users — remove.
    logins = [s["login"] for s in DEMO_USERS]
    users = env["res.users"].search([("login", "in", logins)])
    if users:
        _logger.info("multi_company_example: removing %d demo users", len(users))
        users.unlink()

    # Demo customers — remove only if untouched by transactions.
    customer_names = [s["name"] for s in DEMO_CUSTOMERS]
    customers = env["res.partner"].search([("name", "in", customer_names)])
    for c in customers:
        try:
            c.unlink()
        except Exception:
            _logger.info(
                "multi_company_example: cannot remove customer %s (has refs); archiving",
                c.name,
            )
            c.active = False

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
