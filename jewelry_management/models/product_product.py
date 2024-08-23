from datetime import time, timedelta

from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_round


class ProductProduct(models.Model):
    _inherit = 'product.product'

    purity_id = fields.Many2one('purity',string='Purity')
    making_charge_id = fields.Many2one('making_charge',string='Making Style')
    making_charges_percentages = fields.Float(related='making_charge_id.making_charge',string='Making Charge per (gm)')
    stone_weight = fields.Float(string='Stone Weight')
    stone_rate = fields.Float(string='Stone Rate')
    net_weight = fields.Float(string='Net Weight', store=True)
    gold_weight = fields.Float(string='Weight (gm)')
    gold_waste = fields.Float(string='Gold Waste %')



 

class ProductTemplate(models.Model):
    _inherit = "product.template"

    purity = fields.Many2one('purity',string='Purity')
    making_charge_id = fields.Many2one('making_charge',string='Making Style')
    making_charges_percentages = fields.Float(related='making_charge_id.making_charge',string='Making Charge per (gm)')
    gold_weight = fields.Float(string='Weight (gm)')
    gold_waste = fields.Float(string='Gold Waste %')


    @api.onchange('gold_weight')
    def fetch_weight(self):
        self.weight = self.gold_weight

