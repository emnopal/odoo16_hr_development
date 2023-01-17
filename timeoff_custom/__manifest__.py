{
    "name": "Timeoff Custom",
    "version": "1.0",
    "summary": "Custom module for Odoo Timeoff",
    "sequence": 1,
    "description": """
        Refer to hr_holidays module
    """,
    "category": "Human Resources",
    "website": "",
    "license": "LGPL-3",
    "depends": ['hr', 'calendar', 'resource', 'hr_holidays'],
    "data": [
        "security/ir.model.access.csv",
        'security/security.xml',
        'report/hr_leave_report_view.xml',
        'views/hr_leave_views.xml',
        'views/hr_leave_allocation_views.xml',
        'views/hr_leave_type_views.xml',
        'views/hr_employee.xml',
        'views/hr_employee_public.xml',
    ],
    "demo": [],
    "qweb": [],
    "installable": True,
    "application": True,
    "auto_install": False,
}
