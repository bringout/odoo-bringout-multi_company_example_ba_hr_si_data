"""Migration to 16.0.1.6.1 — wire shared-product taxes, per-company
pricelists, and customer pricelist assignment on already-installed DBs.

The post-init hook only fires on fresh install; this migration backfills
the shared Product 01 / Product 02 tax-id wiring, the per-company
pricelists (with the country-specific prices), and the demo customer
pricelist links so existing multi-test DBs end up in the same state as
a fresh install.
"""

import logging

from odoo import api, SUPERUSER_ID

from odoo.addons.multi_company_example_ba_hr_si_data.hooks import (
    COMPANY_SPECS,
    _ensure_shared_products,
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
            "multi_company_example migration 16.0.1.6.1: no companies found, "
            "skipping pricing setup"
        )
        return
    _ensure_shared_products(env, companies_by_name)
    pricelists_by_company = _ensure_pricelists(env, companies_by_name)
    _assign_pricelists_to_customers(env, companies_by_name, pricelists_by_company)
