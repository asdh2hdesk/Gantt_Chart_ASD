from odoo import models, fields, api
from datetime import date, timedelta
import logging

_logger = logging.getLogger(__name__)

class ProjectDetailsWizard(models.TransientModel):
    _name = 'project.details.wizard'
    _description = 'Project Details Wizard'

    project_id = fields.Many2one('project.project', string='Project')
    wbs_root = fields.Char('WBS Root', required=True)
    project_name = fields.Char('Project Name', compute='_compute_project_name')
    task_ids = fields.Many2many('gantt.task', string='All Tasks', compute='_compute_task_ids', store=False)
    completed_task_ids = fields.Many2many('gantt.task', string='Completed Tasks', compute='_compute_completed_tasks')
    delayed_task_ids = fields.Many2many('gantt.task', string='Delayed Tasks', compute='_compute_delayed_tasks')
    critical_task_ids = fields.Many2many('gantt.task', string='Critical Tasks', compute='_compute_critical_tasks')
    task_line_ids = fields.One2many('project.task.line', 'wizard_id', string='Task Lines')
    total_tasks = fields.Integer('Total Tasks', compute='_compute_task_stats')
    completed_tasks = fields.Integer('Completed Tasks', compute='_compute_task_stats')
    in_progress_tasks = fields.Integer('In Progress Tasks', compute='_compute_task_stats')
    delayed_tasks = fields.Integer('Delayed Tasks', compute='_compute_task_stats')
    project_start_date = fields.Date('Project Start Date', compute='_compute_project_dates')
    project_end_date = fields.Date('Project End Date', compute='_compute_project_dates')
    project_duration = fields.Integer('Project Duration', compute='_compute_project_duration')

    @api.model
    def default_get(self, fields_list):
        res = super().default_get(fields_list)
        _logger.info("Context: %s", self._context)
        wbs_root = self._context.get('default_wbs_root')
        project_id = self._context.get('default_project_id')
        if wbs_root:
            res['wbs_root'] = wbs_root
        if project_id:
            res['project_id'] = project_id
        return res

    @api.onchange('wbs_root', 'project_id')
    def _onchange_project_data(self):
        project_id = self.project_id.id if self.project_id else False
        if not self.wbs_root or not self.project_id or not self.project_id.id:
            self.task_line_ids = [(5, 0, 0)]
            return {
                'warning': {
                    'title': 'Warning',
                    'message': 'Please select a valid project and WBS root.',
                }
            }

        self.task_line_ids = [(5, 0, 0)]
        try:
            tasks = self.env['gantt.task'].search([
                ('project_id', '=', self.project_id.id if self.project_id else False),
                '|',
                ('wbs', '=', self.wbs_root),
                ('wbs', '=like', f'{self.wbs_root}.%')
            ], order='wbs asc')
            tasks = tasks.exists()  # Ensure only valid records
        except Exception as e:
            self.env.cr.rollback()
            self.task_line_ids = [(5, 0, 0)]
            _logger.error(f"Error loading tasks: {str(e)}")
            return {
                'warning': {
                    'title': 'Error',
                    'message': f'Failed to load tasks: {str(e)}',
                }
            }

        task_lines = []
        prefix = f'{self.wbs_root}.'
        for task in tasks:
            if not task.id:
                continue
            stripped_wbs = task.wbs.replace(prefix, '', 1) if task.wbs.startswith(prefix) else task.wbs
            task_lines.append((0, 0, {
                'original_task_id': task.id,
                'wbs': stripped_wbs,
                'name': task.name or 'Unnamed Task',
                'lead': task.lead.id if task.lead else False,
                'start_date': task.start_date or fields.Date.today(),
                'end_date': task.end_date or fields.Date.today() + timedelta(days=7),
                'progress': task.progress or 0.0,
                'priority': task.priority or 'medium',
                'dependencies': task.dependencies or '',
                'description': task.description or '',
            }))
        self.task_line_ids = task_lines

    @api.depends('wbs_root')
    def _compute_project_name(self):
        for wizard in self:
            wizard.project_name = f'Project {wizard.wbs_root}' if wizard.wbs_root else 'Unknown Project'

    @api.depends('wbs_root', 'project_id')
    def _compute_task_ids(self):
        for wizard in self:
            if wizard.wbs_root and wizard.project_id and wizard.project_id.id:
                tasks = self.env['gantt.task'].search([
                    ('project_id', '=', wizard.project_id.id),
                    '|',
                    ('wbs', '=', wizard.wbs_root),
                    ('wbs', '=like', f'{wizard.wbs_root}.%')
                ])
                wizard.task_ids = tasks.exists() or self.env['gantt.task'].browse([])
            else:
                wizard.task_ids = self.env['gantt.task'].browse([])

    @api.depends('task_ids')
    def _compute_completed_tasks(self):
        for wizard in self:
            wizard.completed_task_ids = wizard.task_ids.filtered(lambda t: t.progress == 100) if wizard.task_ids else self.env['gantt.task'].browse([])

    @api.depends('task_ids')
    def _compute_delayed_tasks(self):
        for wizard in self:
            wizard.delayed_task_ids = wizard.task_ids.filtered('is_delayed') if wizard.task_ids else self.env['gantt.task'].browse([])

    @api.depends('task_ids')
    def _compute_critical_tasks(self):
        for wizard in self:
            wizard.critical_task_ids = wizard.task_ids.filtered(lambda t: t.priority in ['high', 'urgent']) if wizard.task_ids else self.env['gantt.task'].browse([])

    @api.depends('task_ids')
    def _compute_task_stats(self):
        for wizard in self:
            tasks = wizard.task_ids
            wizard.total_tasks = len(tasks)
            wizard.completed_tasks = len(tasks.filtered(lambda t: t.progress == 100))
            wizard.in_progress_tasks = len(tasks.filtered(lambda t: 0 < t.progress < 100))
            wizard.delayed_tasks = len(tasks.filtered('is_delayed'))

    @api.depends('task_ids')
    def _compute_project_dates(self):
        for wizard in self:
            tasks = wizard.task_ids
            if tasks:
                start_dates = [t.start_date for t in tasks if t.start_date]
                end_dates = [t.end_date for t in tasks if t.end_date]
                wizard.project_start_date = min(start_dates) if start_dates else False
                wizard.project_end_date = max(end_dates) if end_dates else False
            else:
                wizard.project_start_date = False
                wizard.project_end_date = False

    @api.depends('project_start_date', 'project_end_date')
    def _compute_project_duration(self):
        for wizard in self:
            if wizard.project_start_date and wizard.project_end_date:
                wizard.project_duration = (wizard.project_end_date - wizard.project_start_date).days + 1
            else:
                wizard.project_duration = 0

    def action_create_task(self):
        if not self.project_id or not self.project_id.id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Project is not set. Please select a project.',
                    'type': 'danger',
                }
            }

        existing_lines = self.task_line_ids.filtered(lambda l: l.wbs)
        top_numbers = []
        for line in existing_lines:
            if '.' not in line.wbs:
                try:
                    top_numbers.append(int(line.wbs))
                except ValueError:
                    continue

        next_number = max(top_numbers, default=0) + 1
        next_wbs = str(next_number)
        new_task_line = (0, 0, {
            'wbs': next_wbs,
            'name': f'New Task {next_number}',
            'start_date': fields.Date.today(),
            'end_date': fields.Date.today() + timedelta(days=7),
            'progress': 0,
            'priority': 'medium',
            'dependencies': '',
            'description': '',
            'original_task_id': 0,
        })
        self.write({'task_line_ids': [(0, 0, new_task_line[2])]})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'title': 'Task Added',
                'message': f'Added new task with WBS: {next_wbs}',
                'type': 'success',
            }
        }

    def action_add_task_inline(self):
        existing_lines = self.task_line_ids.filtered(lambda l: l.wbs)
        top_numbers = []
        for line in existing_lines:
            if '.' not in line.wbs:
                try:
                    top_numbers.append(int(line.wbs))
                except ValueError:
                    continue

        next_number = max(top_numbers, default=0) + 1
        next_wbs = str(next_number)
        new_task_line = (0, 0, {
            'wbs': next_wbs,
            'name': f'New Task {next_number}',
            'start_date': fields.Date.today(),
            'end_date': fields.Date.today() + timedelta(days=7),
            'progress': 0,
            'priority': 'medium',
            'dependencies': '',
            'description': '',
        })
        self.write({'task_line_ids': [(0, 0, new_task_line[2])]})
        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
            'params': {
                'title': 'Task Added',
                'message': f'Added new task with WBS: {next_wbs}',
                'type': 'success',
            }
        }

    def action_open_gantt(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'combined_gantt_widget',
            'name': f'Gantt Chart - {self.project_name}',
            'context': {
                'default_wbs_root': self.wbs_root,
                'project_name': self.project_name,
            },
            'target': 'current',
        }

    def action_export_project(self):
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Export',
                'message': 'Export functionality not yet implemented.',
                'type': 'info',
            }
        }

    def action_save_and_close(self):
        if not self.project_id or not self.project_id.id:
            return {
                'type': 'ir.actions.client',
                'tag': 'display_notification',
                'params': {
                    'title': 'Error',
                    'message': 'Project is not set. Cannot save tasks.',
                    'type': 'danger',
                }
            }

        prefix = f'{self.wbs_root}.'
        for line in self.task_line_ids:
            full_wbs = f"{prefix}{line.wbs}"
            vals = {
                'name': line.name,
                'wbs': full_wbs,
                'lead': line.lead.id if line.lead else False,
                'start_date': line.start_date,
                'end_date': line.end_date,
                'progress': line.progress,
                'priority': line.priority,
                'dependencies': line.dependencies or '',
                'description': line.description or '',
                'project_id': self.project_id.id,
            }
            if line.original_task_id:
                existing_task = self.env['gantt.task'].browse(line.original_task_id)
                if existing_task.exists():
                    existing_task.write(vals)
            else:
                self.env['gantt.task'].create(vals)
        return {'type': 'ir.actions.act_window_close'}

    def action_refresh(self):
        self._onchange_project_data()
        return {
            'type': 'ir.actions.client',
            'tag': 'display_notification',
            'params': {
                'title': 'Refreshed',
                'message': f'Reloaded {len(self.task_line_ids)} task lines.',
                'type': 'info',
            }
        }


class ProjectTaskLine(models.TransientModel):
    _name = 'project.task.line'
    _description = 'Project Task Line for Wizard'

    wizard_id = fields.Many2one('project.details.wizard', string='Wizard', ondelete='cascade')
    original_task_id = fields.Many2one('gantt.task', string='Original Task')
    wbs = fields.Char('WBS', required=True)
    name = fields.Char('Project Name', required=True)
    lead = fields.Many2one('res.users', string='Assignee')
    start_date = fields.Date('Start Date', required=True)
    end_date = fields.Date('End Date', required=True)
    duration = fields.Integer(string='Days', compute='_compute_duration')
    progress = fields.Float('Progress (%)', default=0)
    dependencies = fields.Char('Dependencies')
    description = fields.Text('Description')
    is_delayed = fields.Boolean('Delayed', compute='_compute_is_delayed')
    priority = fields.Selection([
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent')
    ], default='medium')

    @api.depends('start_date', 'end_date')
    def _compute_duration(self):
        for rec in self:
            if rec.start_date and rec.end_date:
                rec.duration = (rec.end_date - rec.start_date).days + 1
            else:
                rec.duration = 0

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

    @api.constrains('progress')
    def _check_progress(self):
        for record in self:
            if record.progress < 0 or record.progress > 100:
                raise ValueError("Progress must be between 0 and 100")