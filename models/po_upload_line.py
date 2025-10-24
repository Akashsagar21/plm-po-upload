from odoo import models, fields

class PoUploadLine(models.Model):
    _name = 'po_upload.line'
    _description = 'PO Upload Line'

    upload_id = fields.Many2one('po_upload.upload', string='Upload', ondelete='cascade')
    order_id = fields.Many2one('sale.order', string='SO', readonly=True)

    buyer_order_number = fields.Char(string="Buyer Order Number")
    sku_no = fields.Char(string='SKU No', required=True)
    vendor_code = fields.Float(string='Vendor Code')
    quantity = fields.Float(string='Quantity', required=True)

    order_date = fields.Date(string="Order Date")
    po_issue_date = fields.Date(string="PO Issue Date")
    vendor_ex_fact_date = fields.Date(string="Vendor Ex-Fact Date")

    customer_id = fields.Many2one(
        'res.partner',
        string='Customer',
        domain=[('is_company', '=', True), ('customer_rank', '>', 0)],
        required=True)
    vendor_id = fields.Many2one(
        'res.partner',
        string='Vendor',
        domain=[('is_company', '=', True), ('supplier_rank', '>', 0)],
        required=True)

    # Decoration flags
    is_invalid_sku = fields.Boolean(string='Invalid SKU', default=True,store=True)
    is_valid_sku = fields.Boolean(string='Valid SKU', default=False,store=True)
