from datetime import time, timedelta

from odoo import api, fields, models, _
from odoo.tools import DEFAULT_SERVER_DATETIME_FORMAT, get_lang
from odoo.tools.float_utils import float_compare, float_round
from odoo.exceptions import UserError
import logging
_logger = logging.getLogger(__name__)
from odoo.tools import (
    date_utils,
    email_re,
    email_split,
    float_compare,
    float_is_zero,
    float_repr,
    format_amount,
    format_date,
    formatLang,
    frozendict,
    get_lang,
    groupby,
    index_exists,
    is_html_empty,
)


class PurchaseOrder(models.Model):
    _inherit = 'purchase.order'

    gold_rate = fields.Float(string='Gold Rate (gm)')

    @api.depends_context('lang')
    @api.depends('order_line.taxes_id', 'order_line.price_subtotal', 'amount_total', 'amount_untaxed')
    def _compute_tax_totals(self):
        for order in self:
            order_lines = order.order_line.filtered(lambda x: not x.display_type)
            order.tax_totals = self.env['account.tax']._prepare_tax_totals(
                [x._convert_to_tax_base_line_dict() for x in order_lines],
                order.currency_id or order.company_id.currency_id,
            )
            groups_by_subtotal = order.tax_totals.get('groups_by_subtotal', {})
            total_tax_rate = 0
            total_tax_groups = 0
            for group in groups_by_subtotal.get('Untaxed Amount', []):
                tax_rate = group.get('tax_group_amount', 0) / group.get('tax_group_base_amount', 1)
                total_tax_rate += tax_rate
                total_tax_groups += 1
            if total_tax_groups != 0:
                average_tax_rate = total_tax_rate / total_tax_groups
                average_tax_rate_percentage = average_tax_rate * 100
            if 'Untaxed Amount' in order.tax_totals['groups_by_subtotal']:
                tax_amount = order.tax_totals['groups_by_subtotal']['Untaxed Amount'][0]
                tax_amount['tax_group_amount'] = order.tax_totals.get('amount_untaxed') * (average_tax_rate_percentage / 100)
                formatted_tax_group_amount = '${:,.2f}'.format(tax_amount['tax_group_amount'])
                tax_amount['formatted_tax_group_amount'] = formatted_tax_group_amount
                formatted_tax_group_base_amount = '${:,.2f}'.format(order.tax_totals.get('amount_untaxed'))
                tax_amount['formatted_tax_group_base_amount'] = formatted_tax_group_base_amount
                order.tax_totals['amount_total'] = order.tax_totals.get('amount_untaxed') + tax_amount['tax_group_amount']
                formatted_amount_total = '${:,.2f}'.format(order.tax_totals['amount_total'])
                order.tax_totals['formatted_amount_total'] = formatted_amount_total
            for line in order.order_line:
                for tax in line.taxes_id:
                    tax_amount = (line.price_subtotal * tax.amount/100) + line.price_subtotal
                    line.sudo().write({'price_total': tax_amount})
            order.write({'amount_total': order.tax_totals['amount_total']
                    })
                         
    @api.onchange('partner_id')
    def match_date(self):        
        order_date = self.env['goldrate_perday.jewelry'].search([])
        for dates in order_date:
            if self.date_order.date() == dates.date:
                self.gold_rate = dates.gold_rate

    

class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    product_purity_id = fields.Many2one(string='Purity', comodel_name='purity', ondelete='restrict')
    product_weight = fields.Float(string='Product Weight (gm)')
    product_stone_weight = fields.Float(string='Stone Weight')
    product_net_weight = fields.Float(string='Net Weight')
    product_stone_rate = fields.Float(string='Stone Rate')
    gold_waste = fields.Float(string='Gold Waste %')
    gold_rate = fields.Float(related='order_id.gold_rate',string='Gold Rate (gm)')
    making_charge = fields.Float(string='Making Charge per (gm)')
    labour_charge = fields.Float(string='Labour Charge')
    gold_weight = fields.Float(string='Weight (gm)')


    @api.model_create_multi
    def create(self, vals):
        result = super(PurchaseOrderLine, self).create(vals)
        for res in result:

            if res.product_id:
                res.product_purity_id = res.product_id.purity_id.id or res.product_id.product_tmpl_id.purity.id
                res.product_weight = res.product_qty * res.product_id.weight  
                res.gold_waste = res.product_id.gold_waste or res.product_id.product_tmpl_id.gold_waste
                res.product_stone_rate = res.product_id.stone_rate
                res.making_charge = res.product_id.making_charges_percentages or res.product_id.product_tmpl_id.making_charges_percentages
                res.labour_charge = res.product_weight * res.making_charge
                res.gold_weight = res.product_id.weight or res.product_id.product_tmpl_id.gold_weight
            # Access the gold_weight field for each record
            
        return result
        

    def write(self, vals):
        try:
            if vals['product_qty']:
                vals['gold_weight'] = self.product_id.weight
                vals['product_purity_id'] = self.product_id.purity_id.id or self.product_id.product_tmpl_id.purity.id
                vals['product_weight'] = self.product_id.weight * vals['product_qty']
                vals['labour_charge'] = self.making_charge * vals['product_weight']
           
                res = super().write(vals)
            return res

        except:
            res = super().write(vals)
            return res
    
    def _convert_to_tax_base_line_dict(self):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.

        :return: A python dictionary.
        """
        self.ensure_one()
        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.order_id.partner_id,
            currency=self.order_id.currency_id,
            product=self.product_id,
            taxes=self.taxes_id,
            price_unit=self.price_unit,
            quantity=self.product_qty,
            discount=self.discount,
            price_subtotal=self.price_subtotal,
            labour_charge=self.labour_charge,

        )
      
    def action_add_from_catalog(self, **vals):
        result = super(PurchaseOrderLine, self).action_add_from_catalog()
        order = self.env['purchase.order'].browse(self.env.context.get('order_id'))
        for line in self:
            line.product_weight = line.product_qty * line.product_id.weight
            
        return result

        # self.ensure_one()
        # return self.env['account.tax']._convert_to_tax_base_line_dict(
        #     self,
        #     partner=self.order_id.partner_id,
        #     currency=self.order_id.currency_id,
        #     product=self.product_id,
        #     taxes=self.taxes_id,
        #     price_unit=self.price_unit,
        #     quantity=self.product_qty,
        #     discount=self.discount,
        #     price_subtotal=self.price_subtotal,
        #     labour_charge=self.labour_charge,
        # )


    @api.onchange('product_id' , 'product_qty')
    def _onchange_product_id(self):
        if self.product_id:
            self.product_purity_id = self.product_id.purity_id.id or self.product_id.product_tmpl_id.purity.id
            self.product_weight = self.product_qty * self.product_id.weight
            self.product_stone_weight = self.product_id.stone_weight
            self.product_net_weight = self.product_id.net_weight
            self.gold_waste = self.product_id.gold_waste or self.product_id.product_tmpl_id.gold_waste
            self.product_stone_rate = self.product_id.stone_rate
            self.making_charge = self.product_id.making_charges_percentages or self.product_id.product_tmpl_id.making_charges_percentages
            self.labour_charge = self.product_weight * self.making_charge
            self.gold_weight = self.product_id.gold_weight or self.product_id.product_tmpl_id.gold_weight

    
    @api.depends('product_qty', 'price_unit', 'taxes_id', 'discount','labour_charge')
    def _compute_amount(self):
        for line in self:
            tax_results = self.env['account.tax']._compute_taxes([line._convert_to_tax_base_line_dict()])
            totals = next(iter(tax_results['totals'].values()))
            # amount_untaxed = line.price_unit + self.labour_charge
            amount_untaxed = totals['amount_untaxed'] + line.labour_charge
            amount_tax = totals['amount_tax']

            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax,
            })




class StockMove(models.Model):
    _inherit = 'stock.move'

    receipt_purity_id = fields.Many2one(string='Purity', comodel_name='purity', ondelete='restrict')
    receipt_product_weight = fields.Float(string='Product Weight (gm)')
    receipt_stone_weight = fields.Float(string='Stone Weight')
    receipt_net_weight = fields.Float(string='Net Weight')
    receipt_gold_waste = fields.Float(string='Gold Waste %')
    receipt_gold_weight = fields.Float(string='Weight (gm)')



    @api.depends('purchase_line_id')
    def _compute_jewelry_product(self):
        for move in self:
            if move.purchase_line_id:
                move.receipt_purity_id = move.purchase_line_id.product_purity_id.id
                move.receipt_product_weight = move.purchase_line_id.product_weight
                move.receipt_stone_weight = move.purchase_line_id.product_stone_weight
                move.receipt_net_weight = move.purchase_line_id.product_net_weight
                move.receipt_gold_waste = move.purchase_line_id.gold_waste
                move.receipt_gold_weight = move.purchase_line_id.gold_weight
            if move.sale_line_id:
                move.receipt_purity_id = move.sale_line_id.product_purity_id.id
                move.receipt_product_weight = move.sale_line_id.product_weight
                move.receipt_stone_weight = move.sale_line_id.product_stone_weight
                move.receipt_net_weight = move.sale_line_id.product_net_weight
                move.receipt_gold_waste = move.sale_line_id.gold_waste
                move.receipt_gold_weight = move.sale_line_id.gold_weight

    @api.model_create_multi
    def create(self, values):
        move = super(StockMove, self).create(values)
        move._compute_jewelry_product()
        return move


class AccountMove(models.Model):
    _inherit = "account.move"

    metal_line_ids = fields.One2many(
        'metal.line',
        'invoice_move_id',
        string='Metal Line ', compute='_compute_department_id',

    )
    metal_return = fields.Many2one('stock.picking' , string='Metal Line Transfer' , readonly=True , copy=False)


    @api.depends_context('lang')
    @api.depends(
        'invoice_line_ids.currency_rate',
        'invoice_line_ids.tax_base_amount',
        'invoice_line_ids.tax_line_id',
        'invoice_line_ids.price_total',
        'invoice_line_ids.price_subtotal',
        'invoice_line_ids.labour_charge',
        'invoice_payment_term_id',
        'partner_id',
        'currency_id',
    )
    def _compute_tax_totals(self):
        """ Computed field used for custom widget's rendering.
            Only set on invoices.
        """
        for move in self:
            if move.is_invoice(include_receipts=True):
                base_lines = move.invoice_line_ids.filtered(lambda line: line.display_type == 'product')
                base_line_values_list = [line._convert_to_tax_base_line_dict() for line in base_lines]
                sign = move.direction_sign
                if move.id:
                    # The invoice is stored so we can add the early payment discount lines directly to reduce the
                    # tax amount without touching the untaxed amount.
                    base_line_values_list += [
                        {
                            **line._convert_to_tax_base_line_dict(),
                            'handle_price_include': False,
                            'quantity': 1.0,
                            'price_unit': sign * line.amount_currency,
                        }
                        for line in move.line_ids.filtered(lambda line: line.display_type == 'epd')
                    ]

                kwargs = {
                    'base_lines': base_line_values_list,
                    'currency': move.currency_id or move.journal_id.currency_id or move.company_id.currency_id,
                }

                if move.id:
                    kwargs['tax_lines'] = [
                        line._convert_to_tax_line_dict()
                        for line in move.line_ids.filtered(lambda line: line.display_type == 'tax')
                    ]
                else:
                    # In case the invoice isn't yet stored, the early payment discount lines are not there. Then,
                    # we need to simulate them.
                    epd_aggregated_values = {}
                    for base_line in base_lines:
                        if not base_line.epd_needed:
                            continue
                        for grouping_dict, values in base_line.epd_needed.items():
                            epd_values = epd_aggregated_values.setdefault(grouping_dict, {'price_subtotal': 0.0})
                            epd_values['price_subtotal'] += values['price_subtotal']

                    for grouping_dict, values in epd_aggregated_values.items():
                        taxes = None
                        if grouping_dict.get('tax_ids'):
                            taxes = self.env['account.tax'].browse(grouping_dict['tax_ids'][0][2])

                        kwargs['base_lines'].append(self.env['account.tax']._convert_to_tax_base_line_dict(
                            None,
                            partner=move.partner_id,
                            currency=move.currency_id,
                            taxes=taxes,
                            price_unit=values['price_subtotal'],
                            quantity=1.0,
                            account=self.env['account.account'].browse(grouping_dict['account_id']),
                            analytic_distribution=values.get('analytic_distribution'),
                            price_subtotal=values['price_subtotal'],
                            is_refund=move.move_type in ('out_refund', 'in_refund'),
                            handle_price_include=False,

                        ))
                kwargs['is_company_currency_requested'] = move.currency_id != move.company_id.currency_id
                move.tax_totals = self.env['account.tax']._prepare_tax_totals(**kwargs)
                labour_charge_sum = sum(move.invoice_line_ids.mapped('labour_charge'))
                # move.tax_totals['amount_untaxed'] +=labour_charge_sum
                groups_by_subtotal = move.tax_totals.get('groups_by_subtotal', {})
                total_tax_rate = 0
                total_tax_groups = 0
                for group in groups_by_subtotal.get('Untaxed Amount', []):
                    tax_rate = group.get('tax_group_amount', 0) / group.get('tax_group_base_amount', 1)
                    total_tax_rate += tax_rate
                    total_tax_groups += 1
                if total_tax_groups != 0:
                    average_tax_rate = total_tax_rate / total_tax_groups
                    average_tax_rate_percentage = average_tax_rate * 100
                if 'Untaxed Amount' in move.tax_totals['groups_by_subtotal']:
                    tax_amount = move.tax_totals['groups_by_subtotal']['Untaxed Amount'][0]
                    tax_amount['tax_group_amount'] = move.tax_totals.get('amount_untaxed') * (average_tax_rate_percentage / 100)
                    formatted_tax_group_amount = '${:,.2f}'.format(tax_amount['tax_group_amount'])
                    tax_amount['formatted_tax_group_amount'] = formatted_tax_group_amount
                    formatted_tax_group_base_amount = '${:,.2f}'.format(move.tax_totals.get('amount_untaxed'))
                    tax_amount['formatted_tax_group_base_amount'] = formatted_tax_group_base_amount
                    move.tax_totals['amount_total'] = move.tax_totals.get('amount_untaxed') + tax_amount['tax_group_amount']
                    formatted_amount_total = '${:,.2f}'.format(move.tax_totals['amount_total'])
                    move.tax_totals['formatted_amount_total'] = formatted_amount_total
                for line in move.invoice_line_ids:
                    for tax in line.tax_ids:
                        tax_amount = (line.price_subtotal * tax.amount/100) + line.price_subtotal
                        line.write({'price_total': tax_amount})
                move.write({'amount_total': move.tax_totals['amount_total']})

            #     if move.invoice_cash_rounding_id:
            #         rounding_amount = move.invoice_cash_rounding_id.compute_difference(move.currency_id,
            #                                                                            move.tax_totals['amount_total'])
            #         totals = move.tax_totals
            #         totals['display_rounding'] = True
            #         if rounding_amount:
            #             if move.invoice_cash_rounding_id.strategy == 'add_invoice_line':
            #                 totals['rounding_amount'] = rounding_amount
            #                 totals['formatted_rounding_amount'] = formatLang(self.env, totals['rounding_amount'],
            #                                                                  currency_obj=move.currency_id)
            #             elif move.invoice_cash_rounding_id.strategy == 'biggest_tax':
            #                 if totals['subtotals_order']:
            #                     max_tax_group = max((
            #                         tax_group
            #                         for tax_groups in totals['groups_by_subtotal'].values()
            #                         for tax_group in tax_groups
            #                     ), key=lambda tax_group: tax_group['tax_group_amount'])
            #                     max_tax_group['tax_group_amount'] += rounding_amount
            #                     max_tax_group['formatted_tax_group_amount'] = formatLang(self.env, max_tax_group[
            #                         'tax_group_amount'], currency_obj=move.currency_id)
            #             totals['amount_total'] += rounding_amount
            #             totals['formatted_amount_total'] = formatLang(self.env, totals['amount_total'],
            #                                                           currency_obj=move.currency_id)
            # else:
            #     # Non-invoice moves don't support that field (because of multicurrency: all lines of the invoice share the same currency)
            #     move.tax_totals = None

    

    def action_post(self):
        fine_gold_product = self.env['product.product'].search([('name', '=', 'Fine Gold')], limit=1)
        if self.metal_line_ids:
                if self.line_ids.sale_line_ids:
                    move_ids = []
                    for rec in self.metal_line_ids:
                        move_ids.append((0, 0, {
                        'name': str(rec.id),
                        'sequence': rec.id,
                        'product_id': fine_gold_product.id,
                        'product_uom_qty': abs(rec.quantity),
                        'receipt_purity_id': rec.purity_id.id,
                        'receipt_gold_weight':abs(rec.gold_weight),
                        'receipt_product_weight': abs(rec.product_weight),
                        'description_picking': rec.metal,
                        'location_id': self.partner_shipping_id.property_stock_customer.id,
                        'location_dest_id': self.line_ids.sale_line_ids.order_id.warehouse_id.id,
                    }))
                    picking = self.env['stock.picking'].create({
                        'location_id': self.partner_shipping_id.property_stock_customer.id,
                        'location_dest_id': self.line_ids.sale_line_ids.order_id.warehouse_id.id,
                        'partner_id': self.partner_id.id,
                        'picking_type_id': self.env.ref('stock.picking_type_in').id,
                        'state': 'draft',
                        'name': self.env['ir.sequence'].next_by_code(
                            'metal.line') or _('New'),
                        'move_type': 'direct',
                        'move_ids': move_ids
                    })
                    picking.action_confirm()
                    picking.action_assign()
                    picking.button_validate()
                    picking.move_ids.picked = True
                    self.metal_return = picking.id

                if self.line_ids.purchase_line_id:
                    stock_location = self.env.ref('stock.stock_location_stock')
                    move_ids = []
                    for rec in self.metal_line_ids:
                        move_ids.append((0, 0, {
                            'name': str(rec.id),
                            'product_id': fine_gold_product.id,
                            'quantity': abs(rec.quantity),
                            'product_uom_qty': abs(rec.quantity),
                            'receipt_purity_id': rec.purity_id.id,
                            'receipt_gold_weight':abs(rec.gold_weight),
                            'receipt_product_weight': abs(rec.product_weight),
                            'description_picking': rec.metal,
                            'location_id': stock_location.id,
                            'location_dest_id': self.partner_shipping_id.property_stock_customer.id,
                        }
                        ))
                    picking = self.env['stock.picking'].create({
                        'location_id': stock_location.id,
                        'location_dest_id': self.partner_shipping_id.property_stock_customer.id,
                        'partner_id': self.partner_id.id,
                        'picking_type_id': self.env.ref('stock.picking_type_out').id,
                        'state': 'draft',
                        'name': self.env['ir.sequence'].next_by_code(
                            'metal.line.purchase') or _('New'),
                        'move_type': 'direct',
                        'move_ids': move_ids
                        
                    })
                    picking.button_validate()
                    picking.move_ids.picked = True
                    self.metal_return = picking.id

        moves_with_payments = self.filtered('payment_id')
        other_moves = self - moves_with_payments

        result = super(AccountMove, self).action_post()

        return result

    @api.depends('invoice_line_ids', 'invoice_line_ids.product_id')
    def _compute_department_id(self):
        for rec in self:
            rec.metal_line_ids = False
            fine_gold_product = self.env['product.product'].search([('name', '=', 'Fine Gold')], limit=1)
            for invoice_line in rec.invoice_line_ids:
                if not invoice_line.product_id:
                    metal_line_values = {
                        'invoice_move_id': rec.id,
                        'purity_id': invoice_line.vendor_purity_id.id,
                        'gold_weight': invoice_line.vendor_gold_weight,
                        'product_weight': invoice_line.vendor_product_weight,
                        'product_id': fine_gold_product.id,
                        'unit_price': invoice_line.price_unit,
                        'metal': invoice_line.name,
                        'quantity': invoice_line.quantity,

                    }
                    existing_metal_line = rec.metal_line_ids.filtered(lambda x: x.product_id is False)
                    if existing_metal_line:
                        existing_metal_line.write(metal_line_values)
                    else:
                        new_metal_line = self.env['metal.line'].create(metal_line_values)
                        rec.metal_line_ids |= new_metal_line


class MetalLine(models.Model):
    _name = "metal.line"
    _description = 'pragtech_jwellery_management.metal.line'

    invoice_move_id = fields.Many2one('account.move', string='Account Move')
    product_id = fields.Many2one('product.product', string='Product')
    unit_price = fields.Float(string='Unit Price')
    metal = fields.Char(string='Metal')
    purity_id = fields.Many2one('purity', string='Purity')
    product_weight = fields.Float(string='Product Weight')
    quantity = fields.Float(string='Quantity')
    gold_weight = fields.Float(string='Weight')


class AccountMoveLine(models.Model):
    _inherit = 'account.move.line'

    vendor_purity_id = fields.Many2one(string='Purity', comodel_name='purity',store=True)
    vendor_gold_weight = fields.Float(string='Weight (gm)',store=True)
    vendor_product_weight = fields.Float(string='Product Weight (gm)',store=True)
    vendor_stone_weight = fields.Float(string='Stone Weight', readonly=True)
    vendor_net_weight = fields.Float(string='Net Weight', readonly=True)
    vendor_stone_rate = fields.Float(string='Stone Rate', readonly=True)
    vendor_gold_waste = fields.Float(string='Gold Waste %', readonly=True)
    making_charge = fields.Float(string='Making Charge per (gm)', readonly=True)
    labour_charge = fields.Float(string='Labour Charge', readonly=True)


    @api.onchange('product_id','quantity','name','vendor_gold_weight')
    def _onchange_direct_product_value(self):
        for move in self:
            if move.product_id:
                move.vendor_purity_id = move.product_id.purity_id.id or  move.product_id.product_tmpl_id.purity.id
                # move.vendor_product_weight = move.product_id.weight or move.product_id.product_tmpl_id.weight
                move.vendor_product_weight = move.product_id.weight * move.quantity

                # move.vendor_purity = move.product_id.purity.purity_values or  move.product_id.product_tmpl_id.purity.purity_values
                # move.vendor_product_weight = move.quantity * move.product_id.product_tmpl_id.weight

                move.vendor_stone_weight = move.product_id.stone_weight
                move.vendor_net_weight = move.product_id.net_weight
                move.vendor_stone_rate = move.product_id.stone_rate
                move.vendor_gold_waste = move.product_id.gold_waste or move.product_id.product_tmpl_id.gold_waste
                move.vendor_gold_weight = move.product_id.gold_weight or move.product_id.product_tmpl_id.gold_weight
                move.making_charge = move.product_id.making_charges_percentages or move.product_id.product_tmpl_id.making_charges_percentages
                move.labour_charge = move.making_charge * move.vendor_product_weight
            else:
                move.vendor_product_weight = move.quantity * move.vendor_gold_weight
                
               
    @api.depends('purchase_line_id', 'sale_line_ids')
    def _compute_jewelry_account_product(self):
        for move in self:
            if move.purchase_line_id:
                move.vendor_purity_id = move.purchase_line_id.product_purity_id
                move.vendor_product_weight = move.purchase_line_id.product_weight
                move.vendor_stone_weight = move.purchase_line_id.product_stone_weight
                move.vendor_net_weight = move.purchase_line_id.product_net_weight
                move.vendor_stone_rate = move.purchase_line_id.product_stone_rate
                move.vendor_gold_waste = move.purchase_line_id.gold_waste
                move.vendor_gold_weight = move.purchase_line_id.gold_weight
                move.making_charge = move.purchase_line_id.making_charge
                move.labour_charge = move.purchase_line_id.labour_charge
                
            if move.sale_line_ids:
                move.vendor_purity_id = move.sale_line_ids.product_purity_id
                move.vendor_product_weight = move.sale_line_ids.product_weight
                move.vendor_stone_weight = move.sale_line_ids.product_stone_weight
                move.vendor_net_weight = move.sale_line_ids.product_net_weight
                move.vendor_stone_rate = move.sale_line_ids.product_stone_rate
                move.vendor_gold_waste = move.sale_line_ids.gold_waste
                move.vendor_gold_weight = move.sale_line_ids.gold_weight
                move.making_charge = move.sale_line_ids.making_charge
                move.labour_charge = move.sale_line_ids.labour_charge
            
            else:
                move.vendor_gold_waste = move.product_id.gold_waste or move.product_id.product_tmpl_id.gold_waste
                move.making_charge = move.product_id.making_charges_percentages or move.product_id.product_tmpl_id.making_charges_percentages
                move.labour_charge = move.making_charge * move.vendor_product_weight

    @api.depends('quantity', 'discount', 'price_unit', 'tax_ids', 'currency_id', 'labour_charge')
    def _compute_totals(self):
        for line in self:
            if line.display_type != 'product':
                line.price_total = line.price_subtotal = False
            # Compute 'price_subtotal'.
            line_discount_price_unit = line.price_unit * (1 - (line.discount / 100.0))
            subtotal = line.quantity * line_discount_price_unit

            # Compute 'price_total'.
            if line.tax_ids:
                taxes_res = line.tax_ids.compute_all(
                    line_discount_price_unit,
                    quantity=line.quantity,
                    currency=line.currency_id,
                    product=line.product_id,
                    partner=line.partner_id,
                    is_refund=line.is_refund,
                )
                line.price_subtotal = taxes_res['total_excluded'] + line.labour_charge
                line.price_total = taxes_res['total_included']
            else:
                line.price_total = line.price_subtotal = subtotal


    @api.model_create_multi
    def create(self, values):
        move = super(AccountMoveLine, self).create(values)
        move._compute_jewelry_account_product()

        return move
    
    def write(self,values):
        try:
            if 'labour_charge' in values:
                values['labour_charge'] = self.making_charge * self.vendor_product_weight
                print("_______________values__________________",values)
            move = super(AccountMoveLine, self).write(values)
            return move
        except Exception as e:
            _logger.error(_('Error : %s' %e))


    def _convert_to_tax_base_line_dict(self):
        """ Convert the current record to a dictionary in order to use the generic taxes computation method
        defined on account.tax.
        :return: A python dictionary.
        """
        self.ensure_one()
        is_invoice = self.move_id.is_invoice(include_receipts=True)
        sign = -1 if self.move_id.is_inbound(include_receipts=True) else 1

        return self.env['account.tax']._convert_to_tax_base_line_dict(
            self,
            partner=self.partner_id,
            currency=self.currency_id,
            product=self.product_id,
            taxes=self.tax_ids,
            price_unit=self.price_unit if is_invoice else self.amount_currency,
            quantity=self.quantity if is_invoice else 1.0,
            discount=self.discount if is_invoice else 0.0,
            account=self.account_id,
            analytic_distribution=self.analytic_distribution,
            price_subtotal=sign * self.amount_currency,
            is_refund=self.is_refund,
            rate=(abs(self.amount_currency) / abs(self.balance)) if self.balance else 1.0,
            labour_charge=self.labour_charge,

        )


class StockMoveLine(models.Model):
    _inherit = "stock.move.line"

    receipt_purity_id = fields.Many2one(string='Purity',related='move_id.receipt_purity_id' )
    receipt_product_weight = fields.Float(related='move_id.receipt_product_weight', string='Product Weight')
    receipt_stone_weight = fields.Float(related='move_id.receipt_stone_weight', string='Stone Weight')
    receipt_net_weight = fields.Float(related='move_id.receipt_net_weight', string='Net Weight')
    receipt_gold_waste = fields.Float(related='move_id.receipt_gold_waste',string='Gold Waste %')
    receipt_gold_weight = fields.Float(related='move_id.receipt_gold_weight',string='Weight (gm)')


