"""Migration to 16.0.1.1.0 — ensure DEMO_EMPLOYEES are created on existing installs.

post_init_hook only runs on fresh install. For databases that had the
module at <= 16.0.1.0.0, employees were never created. This migration
reuses the idempotent ``_ensure_demo_employees`` helper.
"""

import logging

from odoo import api, SUPERUSER_ID

from odoo.addons.multi_company_example_ba_hr_si_data.hooks import (
    COMPANY_SPECS,
    _ensure_demo_employees,
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
            "multi_company_example migration 16.0.1.1.0: no companies "
            "found — skipping employee creation"
        )
        return
    _ensure_demo_employees(env, companies_by_name)
