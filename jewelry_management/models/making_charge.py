from odoo import _, api, fields, models, tools
from odoo.exceptions import UserError
from odoo.tools import float_round


class Makingcharge(models.Model):
    _name = 'making_charge'
    _description = 'pragtech_jwellery_management.making_charge'

    name = fields.Char(string='Making Style',required=True)
    making_charge = fields.Float(string='Making Charge per (gm)')


    @api.model_create_multi
    def create(self, values):
        if 'making_charge' in values and values['making_charge'] == 0:
            raise UserError(_("Please add a making charge greater than 0"))
        else:
            result = super(Makingcharge, self).create(values)
            return result
        
  
    def write(self, values):
        if 'making_charge' in values and values['making_charge'] == 0:
            raise UserError(_("Please add a making charge greater than 0"))
        else:
            result = super(Makingcharge, self).write(values)
            return result


  

    

    
