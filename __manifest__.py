{
    'name': 'plm_po_upload',
    'version': '1.0',
    'depends': ['sale_management','product','inspection','contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/sale_order_line_views.xml',
        'views/res_partner_views.xml',
        'views/sale_order_views.xml',
    ],
    'installable': True,
    'application': False,
}
