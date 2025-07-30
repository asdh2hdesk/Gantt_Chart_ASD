{
    'name': 'Dynamic Gantt Chart with Frappe',
    'version': '16.0.0.0',
    'category': 'Project Management',
    'summary': 'Dynamic Gantt charts using Frappe Gantt library',
    'description': """
        This module provides dynamic Gantt chart functionality using the Frappe Gantt library.
        Features:
        - Interactive Gantt charts
        - Task dependencies
        - Progress tracking
        - Drag and drop functionality
    """,
    'author': 'Rakesh ASD',
    'website': 'https://asdsoftwares.com',
    'depends': ['base', 'web', 'project', 'mail'],
    'data': [
        'security/ir.model.access.csv',
        'views/gantt_actions.xml',
        'views/gantt_task_views.xml',
        'views/gantt_menu.xml',
        'views/project_wizard_view.xml'

    ],
    'assets': {
        'web.assets_backend': [
            'gantt_chart/static/src/lib/frappe-gantt.css',
            'gantt_chart/static/src/lib/frappe-gantt.min.js',
            'gantt_chart/static/src/js/frappe_gantt_widget.js',
            'gantt_chart/static/src/js/combined_gantt_widget.js',
            'gantt_chart/static/src/css/combined_gantt.css',
            'gantt_chart/static/src/xml/gantt_templates.xml',
            'https://cdnjs.cloudflare.com/ajax/libs/html2canvas/1.4.1/html2canvas.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/xlsx/0.18.5/xlsx.full.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/jszip/3.10.1/jszip.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/FileSaver.js/2.0.5/FileSaver.min.js',
            'https://cdnjs.cloudflare.com/ajax/libs/exceljs/4.3.0/exceljs.min.js',

        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
