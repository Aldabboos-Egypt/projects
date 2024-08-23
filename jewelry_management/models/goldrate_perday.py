from odoo import _, api, fields, models, tools
from odoo.exceptions import ValidationError

class GoldRate(models.Model):
    _name = 'goldrate_perday.jewelry'
    _description = 'Jewellery GoldRate perday'


    date = fields.Date(string='Date' ,required=True)
    gold_rate = fields.Float(string='Gold Rate/Day')


    _sql_constraints = [
        (
            'uniq_date',
            'unique(date)',
            'No Duplicate Values are allowed'
        ),
    ]


    @api.constrains('gold_rate')
    def _check_gold_rate(self):
        for record in self:
            if record.gold_rate == 0:
                raise ValidationError("Gold Rate must be greater than zero.")


    def cron_jewellery(self):
        today = fields.Date.today()
        latest_record = self.env['goldrate_perday.jewelry'].search([('date', '<=', today)], order='date DESC', limit=1)
        
        # Iterate over all products in product.product
        products = self.env['product.template'].search([])
        for product in products:
            # Calculate the new sale price based on product weight and gold rate
            new_sale_price = product.gold_weight * latest_record.gold_rate
            product.write({'list_price': new_sale_price})


    def min_cron_jewellery(self):
        products = self.env['product.template'].search([])
        for product in products:
            new_sale_price = product.gold_weight * self.gold_rate
            product.write({'list_price': new_sale_price})


        #     # Update the sale price
        
        

