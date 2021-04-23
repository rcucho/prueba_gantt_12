# -*- coding: utf-8 -*-

{
    'name' : 'Cálculo de honorarios médicos',
    'version' : '1.0.1',
    'author' : 'Meditech Solutions',
    'category' : 'Accounting & Finance',
    'summary': 'Módulo para el cálculo de honorarios médicos.',
    'license': 'LGPL-3',
    'description' : """
Cálculo de honorarios médicos
====================================

Módulos:
--------------------------------------------
    * Listado de médicos y honorarios.
    * Listado de estudios por paciente y médicos.

    """,
    'website': 'http://www.meditech-s.com',
    'depends' : ['base','l10n_pe','sale'],
    'data': [
        'views/medicos_views.xml',
        'security/ir.model.access.csv',
    ],
    'installable': True,
    'auto_install': False,
    "sequence": 1,
}
