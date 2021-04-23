# -*- coding: utf-8 -*-

{
    'name' : 'Código de Producto SUNAT',
    'version' : '13.0.1.0.0',
    'author' : 'Mouse Technologies',
    'category' : 'Technical Configuration',
    'summary': 'Adding tracking to contacts',
    'license': 'LGPL-3',
    'description' : "",
    'website': 'https://www.mouse.pe',
    'depends' : [
        'mouse_einvoice_base',
        'mouse_einvoice_patch_25',
    ],
    'data': [
        'views/product_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    "sequence": 1,
}

