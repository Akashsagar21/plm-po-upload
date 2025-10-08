from odoo import models, fields

class PoUpload(models.Model):
    _name = 'po_upload.upload'
    _description = 'PO Upload'
    name = fields.Char(string="Upload Name", unique=True)
    plm_created_by = fields.Many2one('res.users', string="Created By", default=lambda self: self.env.uid, readonly=True)
    plm_create_date = fields.Date(string="create_date", tracking=True)
    description = fields.Text(string="Description")
