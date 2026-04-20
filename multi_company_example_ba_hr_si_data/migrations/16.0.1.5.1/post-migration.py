"""Migration to 16.0.1.5.1 — create per-country demo customers.

Post-init hook only fires on fresh install; existing multi-test DBs
need this backfill so the three ``Test <Country> Kupac`` partners get
created with country-appropriate tax / registry numbers.
"""

import logging

from odoo import api, SUPERUSER_ID

from odoo.addons.multi_company_example_ba_hr_si_data.hooks import (
    COMPANY_SPECS,
    _ensure_demo_customers,
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
            "multi_company_example migration 16.0.1.5.1: no companies found, "
            "skipping demo-customer creation"
        )
        return
    _ensure_demo_customers(env, companies_by_name)
