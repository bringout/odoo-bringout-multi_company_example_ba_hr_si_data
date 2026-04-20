"""Migration to 16.0.1.3.0 — assign payroll-stack marker groups to demo users.

Re-runs ``_ensure_user`` for every spec so existing demo users get the
``group_payroll_stack_ba`` / ``group_payroll_stack_oca`` assignment
wired in this version.
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
            "multi_company_example migration 16.0.1.3.0: no companies found, "
            "skipping stack-group assignment"
        )
        return
    for spec in DEMO_USERS:
        _ensure_user(env, spec, companies_by_name)
