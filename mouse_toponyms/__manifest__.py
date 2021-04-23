# -*- coding: utf-8 -*-

{
    'name': 'Toponimos de Peru',
    'version': '1.0.2',
    'author': 'Mouse Technologies',
    'category': 'Localization/America',
    'summary': 'Departamentos, Provincias y distritos del Peru.',
    'license': 'AGPL-3',
    'description' : """
Localizacion Peruana.
====================================

Clientes y Proveedores:
--------------------------------------------
    * Tabla de Ubigeos
    * Departamentos, provincias y distritos de todo el Perú

    """,
    'website': 'http://www.mstech.pe',
    'depends': ['l10n_pe'],
    'data': [
        'views/res_partner_view.xml',
        'views/res_country_view.xml',
        'data/res_country_data.xml',
    ],
    'installable': True,
    'auto_install': False,
    'application': True,
    "sequence": 1,
}

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
