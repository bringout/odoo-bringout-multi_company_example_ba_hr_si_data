"""Migration to 16.0.1.6.3 — add Test Croatia HR2 kupac.

Creates the second Croatian test customer for CompanyHR-2 and wires
its property_product_pricelist to the HR-2 pricelist. Re-runs the same
helpers as the post-init hook so idempotency is preserved.
"""

import logging

from odoo import api, SUPERUSER_ID

from odoo.addons.multi_company_example_ba_hr_si_data.hooks import (
    COMPANY_SPECS,
    _ensure_demo_customers,
    _ensure_pricelists,
    _assign_pricelists_to_customers,
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
            "multi_company_example migration 16.0.1.6.3: no companies found, "
            "skipping customer creation"
        )
        return
    _ensure_demo_customers(env, companies_by_name)
    pricelists_by_company = _ensure_pricelists(env, companies_by_name)
    _assign_pricelists_to_customers(env, companies_by_name, pricelists_by_company)
