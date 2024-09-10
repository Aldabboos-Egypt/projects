from odoo import _, api, fields, models, tools

class Purity(models.Model):
    _name = 'purity'
    _description = 'pragtech_jwellery_management.purity'
    _rec_name = 'name'

    name = fields.Char(string='Purity', required=True)

    purity_values = fields.Float(string='Value', required=True)

    _sql_constraints = [
        (
            'uniq_purity_values',
            'unique(purity_values)',
            'No Duplicate Values are allowed'
        ),
    ]
    
    

    
