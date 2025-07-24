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
    'depends': ['base', 'web'],
    'data': [
        'security/ir.model.access.csv',
        'views/gantt_task_views.xml',
        'views/gantt_menu.xml',
    ],
    'assets': {
        'web.assets_backend': [
            'gantt_chart/static/src/lib/frappe-gantt.css',
            'gantt_chart/static/src/lib/frappe-gantt.min.js',
            'gantt_chart/static/src/js/frappe_gantt_widget.js',
            'gantt_chart/static/src/xml/gantt_templates.xml',
        ],
    },
    'installable': True,
    'application': True,
    'auto_install': False,
    'license': 'LGPL-3',
}
