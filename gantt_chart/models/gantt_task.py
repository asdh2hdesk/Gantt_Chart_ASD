from odoo import models, fields, api
from datetime import datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class GanttTask(models.Model):
    _name = 'gantt.task'
    _description = 'Gantt Chart Task'
    _order = 'start_date'

    name = fields.Char('Task Name', required=True)
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    progress = fields.Float('Progress (%)', default=0, help="Progress percentage (0-100)")
    dependencies = fields.Char('Dependencies', help="Comma-separated task IDs")
    color = fields.Char('Color', default='#3498db')
    description = fields.Text('Description')
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], default='medium')

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValueError("End date must be after start date")

    @api.constrains('progress')
    def _check_progress(self):
        for record in self:
            if record.progress < 0 or record.progress > 100:
                raise ValueError("Progress must be between 0 and 100")

    @api.model
    def get_gantt_data(self):
        """
        Returns formatted data for Frappe Gantt library
        """
        tasks = []
        try:
            records = self.search([])
            _logger.info(f"Found {len(records)} gantt tasks")

            for record in records:
                # Validate required fields
                if not all([record.name, record.start_date, record.end_date]):
                    _logger.warning(f"Skipping task {record.id} - missing required fields")
                    continue

                # Ensure dates are properly formatted
                start_date = record.start_date.strftime('%Y-%m-%d') if record.start_date else None
                end_date = record.end_date.strftime('%Y-%m-%d') if record.end_date else None

                if not start_date or not end_date:
                    _logger.warning(f"Skipping task {record.id} - invalid dates")
                    continue

                task_data = {
                    'id': str(record.id),
                    'name': record.name,
                    'start': start_date,
                    'end': end_date,
                    'progress': max(0, min(100, record.progress or 0)),  # Ensure 0-100 range
                    'dependencies': record.dependencies or '',
                    'custom_class': f'priority-{record.priority}' if record.priority else '',
                }

                tasks.append(task_data)

            _logger.info(f"Returning {len(tasks)} valid tasks for Gantt chart")
            return tasks

        except Exception as e:
            _logger.error(f"Error in get_gantt_data: {str(e)}")
            return []

    @api.model
    def create_sample_data(self):
        """
        Create sample data for testing the Gantt chart
        """
        sample_tasks = [
            {
                'name': 'Project Planning',
                'start_date': '2024-01-01',
                'end_date': '2024-01-05',
                'progress': 100,
                'priority': 'high',
            },
            {
                'name': 'Design Phase',
                'start_date': '2024-01-06',
                'end_date': '2024-01-15',
                'progress': 75,
                'priority': 'medium',
                'dependencies': '1',
            },
            {
                'name': 'Development',
                'start_date': '2024-01-16',
                'end_date': '2024-01-30',
                'progress': 50,
                'priority': 'high',
                'dependencies': '2',
            },
            {
                'name': 'Testing',
                'start_date': '2024-01-25',
                'end_date': '2024-02-05',
                'progress': 25,
                'priority': 'medium',
                'dependencies': '3',
            },
            {
                'name': 'Deployment',
                'start_date': '2024-02-06',
                'end_date': '2024-02-10',
                'progress': 0,
                'priority': 'urgent',
                'dependencies': '4',
            },
        ]

        created_tasks = []
        for task_data in sample_tasks:
            task = self.create(task_data)
            created_tasks.append(task)

        return created_tasks