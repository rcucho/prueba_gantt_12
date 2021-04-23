# -*- coding: utf-8 -*-

{
    'name' : 'API de conexión a Resonorte',
    'version' : '1.0.0',
    'author' : 'MS Technologies',
    'category' : 'Accounting & Finance',
    'summary': 'Conexión API.',
    'license': 'LGPL-3',
    'description' : """API para la integración con el software RIS Clayer de Resonorte""",
    'website': 'http://www.mstech.pe',
    'depends' : ['mouse_einvoice_base','medicos'],
    'data': [
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    "sequence": 1,
}
