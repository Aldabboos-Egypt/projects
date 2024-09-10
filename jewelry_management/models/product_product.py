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

    gold_value = fields.Float(string='Weight On Hand', compute='_compute_gold_value', store=True)
    gold_value_incoming = fields.Float(string='Weight Incoming', compute='_compute_gold_value', store=True)

    # @api.onchange('gold_weight')
    # def gold_weight_changed(self):
    #     if self.qty_available <=0:
    #         self.gold_weight=0.0


    @api.depends('gold_weight', 'qty_available')
    def _compute_gold_value(self):
        for product in self:
            product.gold_value = product.gold_weight * product.qty_available
            product.gold_value_incoming = product.gold_weight * product.incoming_qty





 

class ProductTemplate(models.Model):
    _inherit = "product.template"

    purity = fields.Many2one('purity',string='Purity')
    making_charge_id = fields.Many2one('making_charge',string='Making Style')
    making_charges_percentages = fields.Float(related='making_charge_id.making_charge',string='Making Charge per (gm)')
    gold_weight = fields.Float(string='Weight (gm)')
    gold_waste = fields.Float(string='Gold Waste %')
    gold_value = fields.Float(string='Weight On Hand', compute='_compute_gold_value', store=True)
    gold_value_incoming = fields.Float(string='Weight Incoming', compute='_compute_gold_value', store=True)

    @api.depends('gold_weight', 'qty_available')
    def _compute_gold_value(self):
        for product in self:
            product.gold_value = product.gold_weight * product.qty_available
            product.gold_value_incoming = product.gold_weight * product.incoming_qty


    @api.onchange('gold_weight')
    def fetch_weight(self):
        self.weight = self.gold_weight

