"""Migration to 16.0.1.2.0 — add per-country payroll clerks.

Adds demo.payroll.hr@hodi.ba (locked to CompanyHR-1) and
demo.payroll.si@hodi.ba (locked to CompanySL-1). Reuses the idempotent
``_ensure_user`` helper so existing users are left untouched (or updated
to the current spec) and the two new ones get created.
"""

import logging

from odoo import api, SUPERUSER_ID

from odoo.addons.multi_company_example_ba_hr_si_data.hooks import (
    COMPANY_SPECS,
    DEMO_USERS,
    _ensure_user,
)

_logger = logging.getLogger(__name__)


def migrate(cr, version):
    del version
    env = api.Environment(cr, SUPERUSER_ID, {})
    companies_by_name = {}
    for name, _country, _currency, _chart in COMPANY_SPECS:
        company = env["res.company"].search([("name", "=", name)], limit=1)
        if company:
            companies_by_name[name] = company
    if not companies_by_name:
        _logger.warning(
            "multi_company_example migration 16.0.1.2.0: no companies "
            "found — skipping user creation"
        )
        return
    for spec in DEMO_USERS:
        _ensure_user(env, spec, companies_by_name)
