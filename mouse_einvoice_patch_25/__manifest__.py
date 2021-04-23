# -*- coding: utf-8 -*-

{
    'name' : 'Catálogo de Productos SUNAT',
    'version' : '13.0.1.0.0',
    'author' : 'Mouse Technologies',
    'category' : 'Technical Configuration',
    'summary': 'Adding tracking to contacts',
    'license': 'LGPL-3',
    'description' : "",
    'website': 'https://www.mouse.pe',
    'depends' : [
        'mouse_einvoice_base',
    ],
    'data': [
        'security/ir.model.access.csv',
        'data/einvoice_data_1.xml',
        'data/einvoice_data_2.xml',
        'data/einvoice_data_3.xml',
        'data/einvoice_data_4.xml',
        'data/einvoice_data_5.xml',
        'views/einvoice_views.xml',
    ],
    'installable': True,
    'auto_install': False,
    "sequence": 1,
}

