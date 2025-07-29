from odoo import models, fields, api
from datetime import date, datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class GanttTask(models.Model):
    _name = 'gantt.task'
    _description = 'Gantt Chart Task'
    _order = 'wbs'
    _inherit = ['mail.thread']

    wbs = fields.Char('S. no.', required=True)
    name = fields.Char('Task Name', required=True)
    lead = fields.Many2one('res.users', string='Assignee')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    is_delayed = fields.Boolean(compute="_compute_is_delayed", store=True)
    duration = fields.Integer(string='Days', compute='_compute_duration', store=True)
    progress = fields.Float('Progress (%)', default=0, help="Progress percentage (0-100)")
    overall_progress = fields.Float('Overall Progress (%)', default=0, help="Overall progress percentage (0-100)", compute="_compute_overall_progress", store=True)
    dependencies = fields.Char('Dependencies', help="Comma-separated task IDs")
    color = fields.Char('Color', default='#3498db')
    description = fields.Text('Description')

    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], default='medium')

    @api.depends('progress', 'wbs')
    def _compute_overall_progress(self):
        for task in self:
            # For main project tasks (like "1", "2", etc. - no dots)
            if task.wbs and '.' not in task.wbs:
                # Get all subtasks for this main task
                subtasks = self.search([
                    ('wbs', '=like', f'{task.wbs}.%')
                ])

                if subtasks:
                    # Calculate average progress of all subtasks
                    total_progress = sum(subtasks.mapped('progress'))
                    task.overall_progress = total_progress / len(subtasks) if len(subtasks) > 0 else 0.0
                else:
                    # If no subtasks, use the task's own progress
                    task.overall_progress = task.progress
            else:
                # For subtasks, use their own progress
                task.overall_progress = task.progress

    @api.model
    def create(self, vals):
        task = super(GanttTask, self).create(vals)
        # Trigger recalculation of parent task's overall progress
        if task.wbs and '.' in task.wbs:
            parent_wbs = task.wbs.split('.')[0]
            parent_task = self.search([('wbs', '=', parent_wbs)], limit=1)
            if parent_task:
                parent_task._compute_overall_progress()
        return task

    def write(self, vals):
        result = super(GanttTask, self).write(vals)
        # If progress changed, update parent task's overall progress
        if 'progress' in vals:
            for task in self:
                if task.wbs and '.' in task.wbs:
                    parent_wbs = task.wbs.split('.')[0]
                    parent_task = self.search([('wbs', '=', parent_wbs)], limit=1)
                    if parent_task:
                        parent_task._compute_overall_progress()
        return result

    def action_view_gantt(self):
        return {
            'type': 'ir.actions.act_window',
            'tag': 'action_combined_gantt_chart_client',
            'name': 'Gantt Chart',
            'view_mode': 'gantt',
            'res_model': 'gantt.task',
            'domain': [('id', 'child_of', self.ids)],
            'context': {'default_parent_id': self.id},
            'target': 'current',
        }

    def action_edit_task(self):
        """Open task edit form"""
        return {
            'name': 'Edit Task',
            'type': 'ir.actions.act_window',
            'res_model': 'gantt.task',
            'res_id': self.id,
            'view_mode': 'form',
            'target': 'new',
        }

    def action_delete_task(self):
        """Delete the task"""
        self.unlink()
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }

    def open_gantt_chart(self):
        """
        Open Gantt chart for a specific project/WBS root
        This method extracts the root WBS from the current task and opens
        the combined Gantt view filtered for that project
        """
        # Get the root WBS (first part before any dot)
        wbs_root = self.wbs.split('.')[0] if self.wbs else '1'

        _logger.info(f"Opening Gantt chart for WBS root: {wbs_root} (from task WBS: {self.wbs})")

        return {
            'type': 'ir.actions.client',
            'tag': 'combined_gantt_widget',
            'name': f'Gantt Chart - Project: {self.name}',
            'context': {
                'default_wbs_root': wbs_root,
                'project_name': f'Project: {self.name}',
            },
            'target': 'current',
        }

    def open_project_details(self):
        """
        Open project details wizard for the project this task belongs to
        """
        # Get the root WBS (first part before any dot)
        wbs_root = self.wbs.split('.')[0] if self.wbs else '1'

        _logger.info(f"Opening project details wizard for WBS root: {wbs_root}")

        return {
            'type': 'ir.actions.act_window',
            'name': f'Project Details - {wbs_root}',
            'res_model': 'project.details.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_wbs_root': wbs_root,
            },
        }

    @api.model
    def open_project_detail(self):
        """
        Open project details wizard for the project this task belongs to
        """
        # Get the root WBS (first part before any dot)
        wbs_root = self.wbs.split('.')[0] if self.wbs else '1'

        _logger.info(f"Opening project details wizard for WBS root: {wbs_root}")

        return {
            'type': 'ir.actions.act_window',
            'name': f'Project Details - {wbs_root}',
            'res_model': 'project.details.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_wbs_root': wbs_root,
            },
        }

    @api.depends('end_date', 'progress')
    def _compute_is_delayed(self):
        today = date.today()
        for task in self:
            if task.end_date and task.progress < 100.0 and task.end_date < today:
                task.is_delayed = True
            else:
                task.is_delayed = False

    @api.constrains('start_date', 'end_date')
    def _check_dates(self):
        for record in self:
            if record.start_date and record.end_date and record.start_date > record.end_date:
                raise ValueError("End date must be after start date")

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                rec.duration = (rec.end_date - rec.start_date).days + 1
            else:
                rec.duration = 0

    @api.constrains('progress')
    def _check_progress(self):
        for record in self:
            if record.progress < 0 or record.progress > 100:
                raise ValueError("Progress must be between 0 and 100")

    @api.model
    def get_gantt_data(self, domain=None, fields=None, wbs_root=None):
        """
        Returns formatted data for Frappe Gantt library
        If wbs_root is provided, filters tasks for that specific project
        """
        tasks = []
        try:
            # Build search domain
            search_domain = domain or []

            # If wbs_root is specified, filter tasks for that project
            if wbs_root:
                # Include exact match and sub-tasks
                wbs_domain = ['|',
                              ('wbs', '=', wbs_root),
                              ('wbs', '=like', f'{wbs_root}.%')]
                search_domain = search_domain + wbs_domain
                _logger.info(f"Filtering tasks for WBS root: {wbs_root}")

            records = self.search(search_domain)
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
                    'id': record.id,  # Keep as integer for consistency
                    'name': record.name,
                    'wbs': record.wbs,
                    'start': start_date,
                    'start_date': start_date,  # Both formats for compatibility
                    'end': end_date,
                    'end_date': end_date,
                    'progress': record.progress or 0,
                    'dependencies': record.dependencies or '',
                    'priority': record.priority or 'medium',
                    'duration': record.duration,
                    'custom_class': f'priority-{record.priority}' if record.priority else '',
                    'lead': record.lead and [record.lead.id, record.lead.name] or False,
                }

                tasks.append(task_data)

            _logger.info(f"Returning {len(tasks)} valid tasks for Gantt chart")
            return tasks

        except Exception as e:
            _logger.error(f"Error in get_gantt_data: {str(e)}")
            return []

    @api.model
    def get_gantt_data_for_project(self, wbs_root):
        """
        Specific method to get Gantt data for a project
        """
        return self.get_gantt_data(wbs_root=wbs_root)

    @api.model
    def create_sample_data(self):
        """
        Create sample data for testing the Gantt chart
        """
        sample_tasks = [
            {
                'name': 'Project Planning',
                'wbs': '1',
                'start_date': '2024-01-01',
                'end_date': '2024-01-05',
                'progress': 100,
                'priority': 'high',
            },
            {
                'name': 'Design Phase',
                'wbs': '1.1',
                'start_date': '2024-01-06',
                'end_date': '2024-01-15',
                'progress': 75,
                'priority': 'medium',
                'dependencies': '1',
            },
            {
                'name': 'Development',
                'wbs': '1.2',
                'start_date': '2024-01-16',
                'end_date': '2024-01-30',
                'progress': 50,
                'priority': 'high',
                'dependencies': '2',
            },
            {
                'name': 'Testing',
                'wbs': '1.3',
                'start_date': '2024-01-25',
                'end_date': '2024-02-05',
                'progress': 25,
                'priority': 'medium',
                'dependencies': '3',
            },
            {
                'name': 'Deployment',
                'wbs': '1.4',
                'start_date': '2024-02-06',
                'end_date': '2024-02-10',
                'progress': 0,
                'priority': 'urgent',
                'dependencies': '4',
            },
            # Second project sample
            {
                'name': 'Project Alpha Planning',
                'wbs': '2',
                'start_date': '2024-02-01',
                'end_date': '2024-02-05',
                'progress': 80,
                'priority': 'high',
            },
            {
                'name': 'Alpha Analysis',
                'wbs': '2.1',
                'start_date': '2024-02-06',
                'end_date': '2024-02-15',
                'progress': 60,
                'priority': 'medium',
                'dependencies': '6',
            },
        ]

        created_tasks = []
        for task_data in sample_tasks:
            task = self.create(task_data)
            created_tasks.append(task)

        return created_tasks