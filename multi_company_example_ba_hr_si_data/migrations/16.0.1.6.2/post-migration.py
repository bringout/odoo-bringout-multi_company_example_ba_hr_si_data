"""Migration to 16.0.1.6.2 — re-apply user group specs.

Adds ``sales_team.group_sale_manager`` to the demo.group.admin user so
it can create sales orders across CompanyHR-1, CompanyHR-2, CompanySL-1,
CompanyBA-1. Runs the same ``_ensure_user`` path as post_init_hook.
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
            "multi_company_example migration 16.0.1.6.2: no companies found, "
            "skipping user-groups update"
        )
        return
    for spec in DEMO_USERS:
        _ensure_user(env, spec, companies_by_name)
