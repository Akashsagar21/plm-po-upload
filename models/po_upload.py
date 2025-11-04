import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError
_logger = logging.getLogger(__name__)

class PoUpload(models.Model):
    _name = 'po_upload.upload'
    _description = 'PO Upload'

    name = fields.Char(string="Name", required=True, copy=False, readonly=True,default=lambda self: _('New'))
    plm_created_by = fields.Many2one('res.users', string="Created By",default=lambda self: self.env.uid, readonly=True)
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
    
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('po_upload.upload') or _('New')
        return super(PoUpload, self).create(vals)
    

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

    # Confirm button
    def action_confirm(self):
        SaleOrder = self.env['sale.order']
        SaleOrderLine = self.env['sale.order.line']

        for record in self:
            if record.state != 'validated':
                raise UserError("Only validated POs can be confirmed.")

            # Log all buyer_order_number values of this PO upload
            buyer_order_numbers = [line.buyer_order_number for line in record.po_lines_ids]
            _logger.info(f"Confirming PO Upload '{record.name}', buyer_order_numbers: {buyer_order_numbers}")

            # Group lines grouped by buyer_order_number (handle missing keys)
            lines_grouped = {}
            for line in record.po_lines_ids:
                key = line.buyer_order_number or 'NO_BUYER_ORDER_NO'
                lines_grouped.setdefault(key, []).append(line)

            _logger.info(f"Number of unique buyer_order_number groups: {len(lines_grouped)}")

            for buyer_order_no, lines in lines_grouped.items():
                _logger.info(f"Creating quotation for buyer_order_number: {buyer_order_no}, lines count: {len(lines)}")

                quotation_vals = {
                    'partner_id': self.env.user.partner_id.id,
                    'origin': record.po_reference,
                    'state': 'draft',
                    'cus_po_upload_no': record.name,
                }
                quotation = SaleOrder.create(quotation_vals)
                _logger.info(f"Quotation created with ID: {quotation.id}")

                for line in lines:
                    product = self.env['product.template'].search([('buyer_style_no', '=', line.sku_no)], limit=1)
                    if product:
                        order_line_vals = {
                            'order_id': quotation.id,
                            'product_id': product.product_variant_id.id,
                            'product_uom_qty': line.quantity if hasattr(line, 'quantity') else 1,
                            'price_unit': product.list_price,
                        }
                        SaleOrderLine.create(order_line_vals)
                        line.write({'order_id': quotation.id})
                        _logger.info(f"Added PO line {line.id} with SKU {line.sku_no} to quotation {quotation.id}")

            record.state = 'confirm'
            _logger.info(f"PO Upload '{record.name}' state updated to confirm")

        return {'type': 'ir.actions.client', 'tag': 'reload'}

   

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
