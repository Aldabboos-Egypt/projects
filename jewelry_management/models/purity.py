from odoo import _, api, fields, models, tools

class Purity(models.Model):
    _name = 'purity'
    _description = 'pragtech_jwellery_management.purity'
    _rec_name = 'purity_values'

    purity_values = fields.Char(string='Purity', required=True)

    _sql_constraints = [
        (
            'uniq_purity_values',
            'unique(purity_values)',
            'No Duplicate Values are allowed'
        ),
    ]
    
    

    
