# -*- coding: utf-8 -*-

{
    'name': 'Factura electronica - Base',
    'version': '2.0.1',
    'author': 'Mouse Technologies',
    'category': 'Accounting & Finance',
    'summary': 'Tablas y requisitos mínimos para la factura electrónica.',
    'license': 'LGPL-3',
    'description' : """
Factura electronica - Base.
====================================

Tablas:
--------------------------------------------
    * Tablas requeridas por la Factura electrónica

    """,
    'website': 'http://www.mstech.pe',
    'depends' : ['base','l10n_pe','mouse_ruc_validation','mouse_toponyms','uom_unece'],
    'data': [
        'views/einvoice_views.xml',
        'views/account_views.xml',
        'views/account_invoice_view.xml',
        'views/product_product_views.xml',
        'views/res_users_view.xml',
        'views/shop_views.xml',
        'data/einvoice_data.xml',
        'data/einvoice_data_part1.xml',
        'data/einvoice_data_part2.xml',
        'data/einvoice_data_part3.xml',
        'data/einvoice_data_part4.xml',
        'data/einvoice_data_part5.xml',
        'data/account_data.xml',
        'security/einvoice_base_security.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    "sequence": 1,
    'post_init_hook': '_create_shop',
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
