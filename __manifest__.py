{
    'name': 'PLM PO Upload',
    'version': '1.0',
    'summary': 'Module to import and validate Purchase Orders',
    'author': 'Akash Sagar',
    'category': 'Purchases',
    'depends': ['sale_management','product','inspection','contacts'],
    'data': [
        'security/ir.model.access.csv',
        'views/po_upload.xml',
        'views/po_upload_line_views.xml',
    ],
    'installable': True,
    'application': True,
}
