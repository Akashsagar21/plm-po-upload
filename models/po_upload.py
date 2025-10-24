import logging
from odoo import models, fields, api
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)

class PoUpload(models.Model):
    _name = 'po_upload.upload'
    _description = 'PO Upload'

    name = fields.Char(string="Name", unique=True)
    plm_created_by = fields.Many2one('res.users', string="Created By",
                                     default=lambda self: self.env.uid, readonly=True)
    plm_create_date = fields.Date(string="Creation Date", tracking=True)
    po_reference = fields.Char(string="PO Reference", tracking=True)
    state = fields.Selection([
        ('new', 'New'),
        ('validated', 'Validated'),
        ('confirm', 'Confirm'),
        ('cancel', 'Cancel'),
    ], default='new', string="State", tracking=True)
    po_lines_ids = fields.One2many('po_upload.line', 'upload_id', string='PO Lines')
     
    has_invalid_sku = fields.Boolean(string="Has Invalid SKU", compute="_compute_sku_status", store=True)
    has_all_valid_sku = fields.Boolean(string="All SKUs Valid", compute="_compute_sku_status", store=True)

    @api.depends('po_lines_ids.is_invalid_sku', 'po_lines_ids.is_valid_sku')
    def _compute_sku_status(self):
        for record in self:
            invalid_lines = record.po_lines_ids.filtered(lambda l: l.is_invalid_sku)
            valid_lines = record.po_lines_ids.filtered(lambda l: l.is_valid_sku)
            record.has_invalid_sku = bool(invalid_lines)
            record.has_all_valid_sku = bool(valid_lines) and not bool(invalid_lines)

    # Cancel button
    def action_cancel(self):
        self.state = 'cancel'

    # Validate button

    def action_validate(self):
        """Validate SKUs based on buyer_style_no in product.template."""
        all_valid = True
        for line in self.po_lines_ids:
            product = self.env['product.template'].search([('buyer_style_no', '=', line.sku_no)], limit=1)
            if product:
                line.write({'is_valid_sku': True, 'is_invalid_sku': False})
                _logger.info(f"Valid SKU found (buyer_style_no match): {line.sku_no}")
            else:
                line.write({'is_valid_sku': False, 'is_invalid_sku': True})
                all_valid = False
                _logger.info(f"Invalid SKU: {line.sku_no}")

        # Update decoration status on parent
        self._compute_sku_status()

        if all_valid:
            self.state = 'validated'
        else:
            self.state = 'new'
        return {'type': 'ir.actions.client', 'tag': 'reload'}
