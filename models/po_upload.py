# -*- coding: utf-8 -*-
import logging
from odoo import models, fields, api, _
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)


class PoUpload(models.Model):
    _name = 'po_upload.upload'
    _description = 'PO Upload'

    name = fields.Char(
        string="Name",
        required=True,
        copy=False,
        readonly=True,
        default=lambda self: _('New'),
    )
    plm_created_by = fields.Many2one(
        'res.users',
        string="Created By",
        default=lambda self: self.env.uid,
        readonly=True,
    )
    plm_create_date = fields.Date(
        string="Creation Date",
        tracking=True,
    )
    po_reference = fields.Char(
        string="PO Reference",
        tracking=True,
    )
    state = fields.Selection(
        [
            ('new', 'New'),
            ('validated', 'Validated'),
            ('confirm', 'Confirm'),
            ('cancel', 'Cancel'),
        ],
        default='new',
        string="State",
        tracking=True,
    )
    po_lines_ids = fields.One2many(
        'po_upload.line',
        'upload_id',
        string='PO Lines',
    )

    has_invalid_sku = fields.Boolean(
        string="Has Invalid SKU",
        compute="_compute_sku_status",
        store=True,
    )
    has_all_valid_sku = fields.Boolean(
        string="All SKUs Valid",
        compute="_compute_sku_status",
        store=True,
    )

    # -------------------------------------------------------------------------
    # CREATE
    # -------------------------------------------------------------------------
    @api.model
    def create(self, vals):
        if vals.get('name', _('New')) == _('New'):
            vals['name'] = self.env['ir.sequence'].next_by_code('po_upload.upload') or _('New')
        return super(PoUpload, self).create(vals)

    # -------------------------------------------------------------------------
    # COMPUTE
    # -------------------------------------------------------------------------
    @api.depends('po_lines_ids.is_invalid_sku', 'po_lines_ids.is_valid_sku')
    def _compute_sku_status(self):
        for record in self:
            invalid_lines = record.po_lines_ids.filtered(lambda l: l.is_invalid_sku)
            valid_lines = record.po_lines_ids.filtered(lambda l: l.is_valid_sku)
            record.has_invalid_sku = bool(invalid_lines)
            record.has_all_valid_sku = bool(valid_lines) and not bool(invalid_lines)

    # -------------------------------------------------------------------------
    # BUTTONS
    # -------------------------------------------------------------------------

    def action_cancel(self):
        """Cancel button."""
        self.state = 'cancel'

    def action_confirm(self):
        """Confirm button: create quotations (sale.order) per buyer_order_number."""
        SaleOrder = self.env['sale.order']
        SaleOrderLine = self.env['sale.order.line']

        for record in self:
            if record.state != 'validated':
                raise UserError(_("Only validated POs can be confirmed."))

            # Log all buyer_order_number values of this PO upload
            buyer_order_numbers = [line.buyer_order_number for line in record.po_lines_ids]
            _logger.info(
                "Confirming PO Upload '%s', buyer_order_numbers: %s",
                record.name,
                buyer_order_numbers,
            )

            # Group lines by buyer_order_number (handle missing keys)
            lines_grouped = {}
            for line in record.po_lines_ids:
                key = line.buyer_order_number or 'NO_BUYER_ORDER_NO'
                lines_grouped.setdefault(key, []).append(line)

            _logger.info(
                "Number of unique buyer_order_number groups: %s",
                len(lines_grouped),
            )

            for buyer_order_no, lines in lines_grouped.items():
                _logger.info(
                    "Creating quotation for buyer_order_number: %s, lines count: %s",
                    buyer_order_no,
                    len(lines),
                )

                # Use the first line of this group as the "header" source
                first_line = lines[0]

                # These field names must exist on po_upload.line
                ex_fact_date = first_line.vendor_ex_fact_date or False
                customer = first_line.customer_id or False
                issue_date = first_line.po_issue_date or False
                vendor = first_line.vendor_id or False

                quotation_vals = {
                    # Customer on the quotation
                    'partner_id': customer.id if customer else False,

                    # Standard fields
                    'origin': record.po_reference,
                    'state': 'draft',

                    # Custom fields on sale.order (must be defined there)
                    'cus_po_issue_date': issue_date,                             # Date
                    'cus_po_upload_no': record.name,                             # Char
                    'cus_buyer_order_no': buyer_order_no
                        if buyer_order_no != 'NO_BUYER_ORDER_NO' else False,     # Char
                    'cus_ex_fact_date': ex_fact_date,                            # Date
                    'vendor_id': vendor.id if vendor else False,                 # Many2one(res.partner)
                }

                _logger.info("Quotation vals: %s", quotation_vals)
                quotation = SaleOrder.create(quotation_vals)
                _logger.info("Quotation created with ID: %s", quotation.id)

                # Create quotation lines
                for line in lines:
                    product_template = self.env['product.template'].search(
                        [('buyer_style_no', '=', line.sku_no)],
                        limit=1,
                    )
                    if product_template:
                        order_line_vals = {
                            'order_id': quotation.id,
                            'product_id': product_template.product_variant_id.id,
                            'product_uom_qty': line.quantity if hasattr(line, 'quantity') else 1,
                            'price_unit': product_template.list_price,
                        }
                        SaleOrderLine.create(order_line_vals)
                        line.write({'order_id': quotation.id})
                        _logger.info(
                            "Added PO line %s with SKU %s to quotation %s",
                            line.id,
                            line.sku_no,
                            quotation.id,
                        )

            record.state = 'confirm'
            _logger.info("PO Upload '%s' state updated to confirm", record.name)

        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_validate(self):
        """Validate SKUs based on buyer_style_no in product.template."""
        all_valid = True
        for line in self.po_lines_ids:
            product = self.env['product.template'].search(
                [('buyer_style_no', '=', line.sku_no)],
                limit=1,
            )
            if product:
                line.write({'is_valid_sku': True, 'is_invalid_sku': False})
                _logger.info("Valid SKU found (buyer_style_no match): %s", line.sku_no)
            else:
                line.write({'is_valid_sku': False, 'is_invalid_sku': True})
                all_valid = False
                _logger.info("Invalid SKU: %s", line.sku_no)

        # Update decoration status on parent
        self._compute_sku_status()

        self.state = 'validated' if all_valid else 'new'
        return {'type': 'ir.actions.client', 'tag': 'reload'}
