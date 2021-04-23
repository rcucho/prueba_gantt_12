# -*- coding: utf-8 -*-

{
    'name' : 'Validador RUC',
    'version' : '1.2.2',
    'author' : 'Mouse Technologies',
    'category' : 'Generic Modules/Base',
    'summary': 'Valida RUC.',
    'license': 'AGPL-3',
    'description' : """
Validador RUC y DNI
-----------------------

Clientes y Proveedores:
-----------------------
    * Nuevo campo "tipo de documento"
    * Validacion RUC y DNI

Créditos:
---------
Este módulo esta basado en el módulo de Alex Cuellar en https://github.com/alexcuellar/l10n_pe_doc_validation

    """,
    'website': 'http://www.mstech.pe',
    'depends' : ['l10n_pe','mouse_toponyms'],
    'data': [
        'views/res_partner_view.xml',
        'views/einvoice_views.xml',
        'data/einvoice_data.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    "sequence": 1,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
