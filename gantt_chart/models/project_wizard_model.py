from odoo import models, fields, api
from datetime import date, timedelta


class ProjectDetailsWizard(models.TransientModel):
    _name = 'project.details.wizard'
    _description = 'Project Details Wizard'

    wbs_root = fields.Char('WBS Root', required=True)
    project_name = fields.Char('Project Name', compute='_compute_project_name')

    # Make task_ids editable by using inverse method
    task_ids = fields.Many2many(
        'gantt.task',
        string='All Tasks',
        compute='_compute_task_ids',
        inverse='_inverse_task_ids',  # Add this for editability
        store=False
    )

    completed_task_ids = fields.Many2many('gantt.task', string='Completed Tasks', compute='_compute_completed_tasks')
    delayed_task_ids = fields.Many2many('gantt.task', string='Delayed Tasks', compute='_compute_delayed_tasks')
    critical_task_ids = fields.Many2many('gantt.task', string='Critical Tasks', compute='_compute_critical_tasks')

    # Statistics
    total_tasks = fields.Integer('Total Tasks', compute='_compute_task_stats')
    completed_tasks = fields.Integer('Completed Tasks', compute='_compute_task_stats')
    in_progress_tasks = fields.Integer('In Progress Tasks', compute='_compute_task_stats')
    delayed_tasks = fields.Integer('Delayed Tasks', compute='_compute_task_stats')

    # Project info
    project_start_date = fields.Date('Project Start Date', compute='_compute_project_dates')
    project_end_date = fields.Date('Project End Date', compute='_compute_project_dates')
    project_duration = fields.Integer('Project Duration', compute='_compute_project_duration')
    # overall_progress = fields.Float('Overall Progress', compute='_compute_overall_progress')

    @api.depends('wbs_root')
    def _compute_project_name(self):
        for wizard in self:
            wizard.project_name = f'Project {wizard.wbs_root}' if wizard.wbs_root else 'Unknown Project'

    @api.depends('wbs_root')
    def _compute_task_ids(self):
        for wizard in self:
            if wizard.wbs_root:
                tasks = self.env['gantt.task'].search([
                    '|', ('wbs', '=', wizard.wbs_root),
                    ('wbs', '=like', f'{wizard.wbs_root}.%')
                ])
                wizard.task_ids = tasks
            else:
                wizard.task_ids = self.env['gantt.task']

    def _inverse_task_ids(self):
        """This method is called when task_ids is modified"""
        # The changes are automatically saved to the original records
        # because we're directly referencing gantt.task records
        pass

    @api.depends('task_ids')
    def _compute_completed_tasks(self):
        for wizard in self:
            wizard.completed_task_ids = wizard.task_ids.filtered(lambda t: t.progress == 100)

    @api.depends('task_ids')
    def _compute_delayed_tasks(self):
        for wizard in self:
            wizard.delayed_task_ids = wizard.task_ids.filtered('is_delayed')

    @api.depends('task_ids')
    def _compute_critical_tasks(self):
        for wizard in self:
            wizard.critical_task_ids = wizard.task_ids.filtered(lambda t: t.priority in ['high', 'urgent'])

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
                wizard.project_start_date = min(tasks.mapped('start_date'))
                wizard.project_end_date = max(tasks.mapped('end_date'))
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

    # Action methods referenced in the XML view
    def action_create_task(self):
        """Create a new task for this project"""
        return {
            'name': 'Create New Task',
            'type': 'ir.actions.act_window',
            'res_model': 'gantt.task',
            'view_mode': 'form',
            'target': 'new',
            'context': {
                'default_wbs': f"{self.wbs_root}.{len(self.task_ids) + 1}",
                'default_start_date': fields.Date.today(),
                'default_end_date': fields.Date.today() + timedelta(days=1),
            },
        }

    def action_open_gantt(self):
        """Open Gantt chart for this project"""
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
        """Export project data (placeholder - implement as needed)"""
        return {
            'type': 'ir.actions.act_url',
            'url': f'/web/content/?model=project.details.wizard&id={self.id}&field=export_data&download=true',
            'target': 'new',
        }

    def action_save_and_close(self):
        """Save all changes and close the wizard"""
        # Changes are automatically saved due to inverse method
        # Just close the wizard
        return {'type': 'ir.actions.act_window_close'}

    def action_refresh(self):
        """Refresh the wizard data"""
        # Force recomputation of all computed fields
        self._compute_task_ids()
        self._compute_completed_tasks()
        self._compute_delayed_tasks()
        self._compute_critical_tasks()
        self._compute_task_stats()
        self._compute_project_dates()
        self._compute_project_duration()

        return {
            'type': 'ir.actions.client',
            'tag': 'reload',
        }


# Alternative approach using One2many with a different relation
class ProjectDetailsWizardAlternative(models.TransientModel):
    _name = 'project.details.wizard.alt'
    _description = 'Project Details Wizard Alternative'

    wbs_root = fields.Char('WBS Root', required=True)
    project_name = fields.Char('Project Name', compute='_compute_project_name')

    # Use One2many with editable lines
    task_line_ids = fields.One2many(
        'project.task.line',
        'wizard_id',
        string='Tasks',
        compute='_compute_task_lines'
    )

    @api.depends('wbs_root')
    def _compute_project_name(self):
        for wizard in self:
            wizard.project_name = f'Project {wizard.wbs_root}' if wizard.wbs_root else 'Unknown Project'

    @api.depends('wbs_root')
    def _compute_task_lines(self):
        """Create editable task lines from gantt.task records"""
        for wizard in self:
            if wizard.wbs_root:
                # Clear existing lines
                wizard.task_line_ids.unlink()

                # Get original tasks
                tasks = self.env['gantt.task'].search([
                    '|', ('wbs', '=', wizard.wbs_root),
                    ('wbs', '=like', f'{wizard.wbs_root}.%')
                ])

                # Create task lines
                lines = []
                for task in tasks:
                    lines.append((0, 0, {
                        'original_task_id': task.id,
                        'wbs': task.wbs,
                        'name': task.name,
                        'lead': task.lead.id if task.lead else False,
                        'start_date': task.start_date,
                        'end_date': task.end_date,
                        'progress': task.progress,
                        'priority': task.priority,
                        'dependencies': task.dependencies,
                        'description': task.description,
                    }))

                wizard.task_line_ids = lines

    def action_save_changes(self):
        """Save all task line changes back to original gantt.task records"""
        for line in self.task_line_ids:
            if line.original_task_id:
                original_task = self.env['gantt.task'].browse(line.original_task_id)
                if original_task.exists():
                    original_task.write({
                        'name': line.name,
                        'lead': line.lead.id if line.lead else False,
                        'start_date': line.start_date,
                        'end_date': line.end_date,
                        'progress': line.progress,
                        'priority': line.priority,
                        'dependencies': line.dependencies,
                        'description': line.description,
                    })

        return {'type': 'ir.actions.act_window_close'}


class ProjectTaskLine(models.TransientModel):
    _name = 'project.task.line'
    _description = 'Project Task Line for Wizard'

    wizard_id = fields.Many2one('project.details.wizard', string='Wizard', ondelete='cascade')

    original_task_id = fields.Integer('Original Task ID')

    # Task fields (editable copies)
    wbs = fields.Char('WBS', required=True)
    name = fields.Char('Task Name', required=True)
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