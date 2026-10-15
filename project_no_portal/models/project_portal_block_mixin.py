# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)
from odoo import models
from odoo.fields import Domain


class ProjectPortalBlockMixin(models.AbstractModel):
    _name = "project.portal.block.mixin"
    _description = "Deny portal users access for companies that block it"

    def _portal_block_restricted_user(self):
        # Only portal users (outside superuser mode) are subject to the block.
        return not self.env.su and self.env.user._is_portal()

    def _portal_block_company(self):
        # A record with no company falls back to the current company.
        self.ensure_one()
        return self.company_id or self.env.company

    def _portal_block_domain(self):
        keep = Domain("company_id.block_project_portal_access", "=", False)
        # company_id is False -> falls back to the current company.
        if not self.env.company.block_project_portal_access:
            keep |= Domain("company_id", "=", False)
        return keep

    def _access_domain(self, operation):
        # Searches and access checks of portal users both use this domain.
        # It is not cached because it depends on the current company.
        domain = super()._access_domain(operation)
        if not self._portal_block_restricted_user():
            return domain
        return domain & self._portal_block_domain()
