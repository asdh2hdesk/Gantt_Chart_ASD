from odoo import models, fields, api
from datetime import date, datetime, timedelta
import logging

_logger = logging.getLogger(__name__)


class GanttTask(models.Model):
    _name = 'gantt.task'
    _description = 'Gantt Chart Task'
    _order = 'wbs'
    _inherit = ['mail.thread']

    project_id = fields.Many2one('project.project', string='Project')
    wbs = fields.Char('S. no.', required=True)
    name = fields.Char('Project Name', required=True)
    lead = fields.Many2one('res.users', string='Assignee')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    is_delayed = fields.Boolean(compute="_compute_is_delayed", store=True)
    duration = fields.Integer(string='Days', compute='_compute_duration', store=True)
    progress = fields.Float('Progress (%)', default=0, help="Progress percentage (0-100)")
    overall_progress = fields.Float('Overall Progress (%)', default=0, help="Overall progress percentage (0-100)",
                                    compute="_compute_overall_progress", store=True)
    dependencies = fields.Char('Dependencies', help="Comma-separated task IDs")
    color = fields.Char('Color', default='#3498db')
    description = fields.Text('Description')

    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], default='medium')

    # Helper method to safely get project info (simplified version)
    def _get_project_info(self):
        """Safely get project information without causing errors"""
        try:
            project_field = getattr(self, 'project_id', None)
            if project_field and hasattr(project_field, 'id'):
                return {'id': project_field.id, 'name': getattr(project_field, 'name', 'Unknown Project')}
            elif project_field:
                return {'id': project_field if isinstance(project_field, (int, float)) else False,
                        'name': 'Unknown Project'}
            else:
                return {'id': False, 'name': 'No Project'}
        except Exception as e:
            _logger.warning(f"Error getting project info for task {self.id}: {str(e)}")
            return {'id': False, 'name': 'No Project'}

    @api.model
    def create(self, vals):
        """Override create - simplified version without project auto-linking"""
        # Don't try to auto-create projects, just create the task
        task = super(GanttTask, self).create(vals)

        # Trigger recalculation of parent task's overall progress
        if task.wbs and '.' in task.wbs:
            parent_wbs = task.wbs.split('.')[0]
            parent_task = self.search([('wbs', '=', parent_wbs)], limit=1)
            if parent_task:
                parent_task._compute_overall_progress()
        return task

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

    def action_link_to_project(self):
        """Simplified action - just show a message instead of complex wizard"""
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Project Linking',
                'message': 'Project linking feature requires the project module to be installed and configured.',
                'type': 'info',
                'sticky': True,
            }
        }

    def open_gantt_chart(self):
        """
        Open Gantt chart for a specific project/WBS root
        This method extracts the root WBS from the current task and opens
        the combined Gantt view filtered for that project
        """
        # Ensure project is linked
        self._ensure_project_link()

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

    def _ensure_project_link(self):
        """Ensure task has a project link, create default if needed"""
        if not self.project_id:
            # Find or create default project
            default_project = self.env['project.project'].search([
                ('name', '=', 'Default Gantt Project')
            ], limit=1)

            if not default_project:
                try:
                    default_project = self.env['project.project'].create({
                        'name': 'Default Gantt Project',
                        'description': 'Auto-created project for Gantt tasks'
                    })
                    _logger.info(f"Created default project: {default_project.name}")
                except Exception as e:
                    _logger.error(f"Failed to create default project: {str(e)}")
                    return False

            # Link task to default project
            try:
                self.write({'project_id': default_project.id})
                _logger.info(f"Linked task {self.id} to project {default_project.name}")
            except Exception as e:
                _logger.error(f"Failed to link task to project: {str(e)}")
                return False

        return True

    from odoo.exceptions import UserError

    def open_project_details(self):
        self.ensure_one()  # Make sure only one record is selected
        project = self
        if not project.exists():
            raise UserError("The selected project does not exist.")

        return {
            'name': 'Project Details',
            'type': 'ir.actions.act_window',
            'res_model': 'project.details.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_project_id': self.id,
                'default_wbs_root': project.wbs,
            }
        }

    def action_fix_project_links(self):
        """Batch action to fix all tasks without project links"""
        tasks_without_project = self.search([('project_id', '=', False)])

        if not tasks_without_project:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Issues Found',
                    'message': 'All tasks are properly linked to projects.',
                    'type': 'info',
                    'sticky': False,
                }
            }

        # Fix all unlinked tasks
        default_project = self.env['project.project'].search([
            ('name', '=', 'Default Gantt Project')
        ], limit=1)

        if not default_project:
            default_project = self.env['project.project'].create({
                'name': 'Default Gantt Project',
                'description': 'Auto-created project for unlinked Gantt tasks'
            })

        tasks_without_project.write({'project_id': default_project.id})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Tasks Fixed',
                'message': f'Successfully linked {len(tasks_without_project)} tasks to the default project.',
                'type': 'success',
                'sticky': False,
            }
        }

    def action_fix_project_links(self):
        """Batch action to fix all tasks without project links"""
        tasks_without_project = self.search([('project_id', '=', False)])

        if not tasks_without_project:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'No Issues Found',
                    'message': 'All tasks are properly linked to projects.',
                    'type': 'info',
                    'sticky': False,
                }
            }

        # Fix all unlinked tasks
        default_project = self.env['project.project'].search([
            ('name', '=', 'Default Gantt Project')
        ], limit=1)

        if not default_project:
            default_project = self.env['project.project'].create({
                'name': 'Default Gantt Project',
                'description': 'Auto-created project for unlinked Gantt tasks'
            })

        tasks_without_project.write({'project_id': default_project.id})

        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Tasks Fixed',
                'message': f'Successfully linked {len(tasks_without_project)} tasks to the default project.',
                'type': 'success',
                'sticky': False,
            }
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
        # Ensure we have a project to link to
        sample_project = self.env['project.project'].search([
            ('name', '=', 'Sample Gantt Project')
        ], limit=1)

        if not sample_project:
            sample_project = self.env['project.project'].create({
                'name': 'Sample Gantt Project',
                'description': 'Sample project for Gantt chart testing'
            })

        sample_tasks = [
            {
                'name': 'Project Planning',
                'wbs': '1',
                'start_date': '2024-01-01',
                'end_date': '2024-01-05',
                'progress': 100,
                'priority': 'high',
                'project_id': sample_project.id,
            },
            {
                'name': 'Design Phase',
                'wbs': '1.1',
                'start_date': '2024-01-06',
                'end_date': '2024-01-15',
                'progress': 75,
                'priority': 'medium',
                'dependencies': '1',
                'project_id': sample_project.id,
            },
            {
                'name': 'Development',
                'wbs': '1.2',
                'start_date': '2024-01-16',
                'end_date': '2024-01-30',
                'progress': 50,
                'priority': 'high',
                'dependencies': '2',
                'project_id': sample_project.id,
            },
            {
                'name': 'Testing',
                'wbs': '1.3',
                'start_date': '2024-01-25',
                'end_date': '2024-02-05',
                'progress': 25,
                'priority': 'medium',
                'dependencies': '3',
                'project_id': sample_project.id,
            },
            {
                'name': 'Deployment',
                'wbs': '1.4',
                'start_date': '2024-02-06',
                'end_date': '2024-02-10',
                'progress': 0,
                'priority': 'urgent',
                'dependencies': '4',
                'project_id': sample_project.id,
            },
            # Second project sample
            {
                'name': 'Project Alpha Planning',
                'wbs': '2',
                'start_date': '2024-02-01',
                'end_date': '2024-02-05',
                'progress': 80,
                'priority': 'high',
                'project_id': sample_project.id,
            },
            {
                'name': 'Alpha Analysis',
                'wbs': '2.1',
                'start_date': '2024-02-06',
                'end_date': '2024-02-15',
                'progress': 60,
                'priority': 'medium',
                'dependencies': '6',
                'project_id': sample_project.id,
            },
        ]

        created_tasks = []
        for task_data in sample_tasks:
            task = self.create(task_data)
            created_tasks.append(task)

        return created_tasks


class GanttTaskProjectLinkWizard(models.TransientModel):
    _name = 'gantt.task.project.link.wizard'
    _description = 'Wizard to Link Gantt Task to Project'

    task_id = fields.Many2one('gantt.task', string='Task')
    task_name = fields.Char(related='task_id.name', string='Task Name')
    current_project_id = fields.Many2one('project.project', string='Current Project')
    new_project_id = fields.Many2one('project.project', string='Select Project')

    show_error_message = fields.Boolean(default=False)
    error_message = fields.Text()

    create_new_project = fields.Boolean('Create New Project', default=False)
    new_project_name = fields.Char('New Project Name')
    new_project_description = fields.Text('Project Description')

    @api.onchange('create_new_project')
    def _onchange_create_new_project(self):
        if self.create_new_project:
            self.new_project_id = False
        else:
            self.new_project_name = False
            self.new_project_description = False

    def action_link_project(self):
        """Link the task to the selected project"""
        if self.create_new_project:
            if not self.new_project_name:
                raise ValueError("Please enter a name for the new project")

            # Create new project
            new_project = self.env['project.project'].create({
                'name': self.new_project_name,
                'description': self.new_project_description or '',
            })
            project_to_link = new_project
        else:
            if not self.new_project_id:
                raise ValueError("Please select a project")
            project_to_link = self.new_project_id

        # Link the task to the project
        self.task_id.write({'project_id': project_to_link.id})

        # Show success message and open project details
        return {
            'type': 'ir.actions.act_window',
            'name': f'Project Details - {self.task_id.wbs.split(".")[0] if self.task_id.wbs else "1"}',
            'res_model': 'project.details.wizard',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_wbs_root': self.task_id.wbs.split('.')[0] if self.task_id.wbs else '1',
                'default_project_id': project_to_link.id,
            },
        }

    def action_cancel(self):
        """Cancel the wizard"""
        return {'type': 'ir.actions.act_window_close'}

    # Add this method to your GanttTask model for easy bulk linking
    def action_bulk_link_projects(self):
        """Bulk link tasks to projects"""
        # Get all unlinked tasks
        unlinked_tasks = self.search([('project_id', '=', False)])

        if not unlinked_tasks:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Info',
                    'message': 'All tasks are already linked to projects.',
                    'type': 'info',
                }
            }

        # Get the first available project (you can modify this logic)
        available_project = self.env['project.project'].search([], limit=1)

        if available_project:
            unlinked_tasks.write({'project_id': available_project.id})
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Success',
                    'message': f'Linked {len(unlinked_tasks)} tasks to project: {available_project.name}',
                    'type': 'success',
                }
            }

    # Add this method to your GanttTask model in gantt_task.py

    # def _ensure_project_link(self):
    #     """Ensure task has a project link, create default if needed"""
    #     if not self.project_id:
    #         # Find or create default project
    #         default_project = self.env['project.project'].search([
    #             ('name', '=', 'Default Gantt Project')
    #         ], limit=1)
    #
    #         if not default_project:
    #             try:
    #                 default_project = self.env['project.project'].create({
    #                     'name': 'Default Gantt Project',
    #                     'description': 'Auto-created project for Gantt tasks'
    #                 })
    #             except Exception as e:
    #                 _logger.error(f"Failed to create default project: {str(e)}")
    #                 return False
    #
    #         # Link task to default project
    #         try:
    #             self.write({'project_id': default_project.id})
    #         except Exception as e:
    #             _logger.error(f"Failed to link task to project: {str(e)}")
    #             return False
    #
    #     return True

    # def open_project_details(self):
    #     """Open project details wizard with automatic project linking"""
    #     self.ensure_one()
    #
    #     # Ensure project link exists FIRST
    #     if not self._ensure_project_link():
    #         return {
    #             'type': 'ir.actions.client',
    #             'tag': 'display_notification',
    #             'params': {
    #                 'title': 'Setup Required',
    #                 'message': 'Please install the project module first or contact your administrator.',
    #                 'type': 'warning',
    #                 'sticky': True,
    #             }
    #         }
    #
    #     wbs_root = self.wbs.split('.')[0] if self.wbs else '1'
    #
    #     return {
    #         'type': 'ir.actions.act_window',
    #         'name': f'Project Details - {wbs_root}',
    #         'res_model': 'project.details.wizard',
    #         'view_mode': 'form',
    #         'target': 'new',
    #         'context': {
    #             'default_wbs_root': wbs_root,
    #             'default_project_id': self.project_id.id,
    #         },
    #     }

    # Also add this method to automatically fix all existing tasks:
    @api.model
    def fix_all_project_links(self):
        """Fix all tasks that don't have project links"""
        unlinked_tasks = self.search([('project_id', '=', False)])

        if not unlinked_tasks:
            return True

        # Find or create default project
        default_project = self.env['project.project'].search([
            ('name', '=', 'Default Gantt Project')
        ], limit=1)

        if not default_project:
            default_project = self.env['project.project'].create({
                'name': 'Default Gantt Project',
                'description': 'Auto-created project for Gantt tasks'
            })

        # Link all unlinked tasks
        unlinked_tasks.write({'project_id': default_project.id})

        _logger.info(f"Fixed {len(unlinked_tasks)} tasks without project links")
        return True