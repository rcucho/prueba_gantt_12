{
    'name': "Mouse Invoice Merge",
    "category": "Invoicing",
    'author': "Mouse Technologies",
    'summary':"""Merge Draft Account Invoice.""",
    'depends': [
        'mouse_einvoice_base',
    ],
    'data': [
        'view/account_invoice_merge.xml',
    ],
    'installable' : True,
    'auto_install' :  False,
    'application' :  False,
}
