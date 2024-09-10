from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import float_round
# -*- coding: utf-8 -*-
from odoo import api, fields, models, _, Command
from odoo.osv import expression
from odoo.tools.float_utils import float_round
from odoo.exceptions import UserError, ValidationError
from odoo.tools.misc import clean_context, formatLang
from odoo.tools import frozendict, groupby, split_every

from collections import defaultdict
from markupsafe import Markup

import ast
import math
import re


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    gold_rate = fields.Float(string='Gold Rate (gm)')

    @api.depends('order_line.tax_id', 'order_line.price_unit', 'amount_total', 'amount_untaxed', 'currency_id','order_line.labour_charge')
    def _compute_tax_totals(self):
        for order in self:
            try:
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
                    for tax in line.tax_id:
                        tax_amount = (line.price_subtotal * tax.amount/100) + line.price_subtotal
                        line.write({'price_total': tax_amount})
                order.write({'amount_total': order.tax_totals['amount_total']
                        })
            except:
                pass
        # for order in self:
        #     order_lines = order.order_line.filtered(lambda x: not x.display_type)
        #     order.tax_totals = self.env['account.tax']._prepare_tax_totals(
        #         [x._convert_to_tax_base_line_dict() for x in order_lines],
        #         order.currency_id or order.company_id.currency_id,
        #     )
        #     if 'amount_untaxed' in order.tax_totals:
        #         order.tax_totals['amount_untaxed'] += sum(order_lines.mapped('labour_charge'))
    @api.onchange('partner_id')
    def match_date(self):        
        order_date = self.env['goldrate_perday.jewelry'].search([])
        for dates in order_date:
            if self.date_order.date() == dates.date:
                self.gold_rate = dates.gold_rate

class SaleOrderOrderLine(models.Model):
    _inherit = 'sale.order.line'

   
    product_purity_id = fields.Many2one(string='Purity', comodel_name='purity', ondelete='restrict')
    product_weight = fields.Float(string='Product Weight (gm)',compute="calculate_total_weight" )
    product_stone_weight = fields.Float(string='Stone Weight')
    product_net_weight = fields.Float(string='Net Weight')
    product_stone_rate = fields.Float(string='Stone Rate ')
    making_charge = fields.Float(string='Making Charge per (gm)')
    labour_charge = fields.Float(string='Labour Charge',compute="calculate_total_weight")
    gold_waste = fields.Float(string='Gold Waste %')
    gold_rate = fields.Float(related='order_id.gold_rate',string='Gold Rate (gm)')
    gold_weight = fields.Float(string='Weight (gm) ')


    @api.onchange('product_id', 'product_uom_qty', 'product_purity_id','gold_rate')
    def _onchange_product_purity(self):
        if self.product_id and self.product_purity_id:
            # Convert purity to an integer
            purity_value = self.product_purity_id.purity_values
            # Calculate the unit price using the formula (rate_24 * purity) / 24
            self.price_unit = (self.gold_rate * purity_value)



    @api.onchange('product_id','product_uom_qty')
    def _onchange_product_id(self):
        for rec in self:
            if rec.product_id:
                rec.product_purity_id = rec.product_id.purity.id or rec.product_id.product_tmpl_id.purity.id
                rec.product_weight = rec.product_id.weight * rec.product_uom_qty
                rec.product_stone_weight = rec.product_id.stone_weight
                rec.product_net_weight = rec.product_id.net_weight
                rec.gold_waste = rec.product_id.gold_waste  or rec.product_id.product_tmpl_id.gold_waste
                rec.making_charge = rec.product_id.making_charges_percentages or rec.product_id.product_tmpl_id.making_charges_percentages
                rec.labour_charge = rec.making_charge * rec.product_weight
                rec.product_stone_rate = rec.product_id.stone_rate
                rec.gold_weight = rec.product_id.gold_weight or rec.product_id.product_tmpl_id.gold_weight

    
        

    @api.model_create_multi
    def create(self, values):

        # Call super method to perform the default behavior of create

        rec = super(SaleOrderOrderLine, self).create(values)
        for records in rec :
            # Update the fields based on the selected product
            if records.product_id:
                records.product_purity_id = records.product_id.purity.id or records.product_id.product_tmpl_id.purity.id
                records.product_weight = records.product_id.weight * records.product_uom_qty
                records.product_stone_weight = records.product_id.stone_weight
                records.product_net_weight = records.product_id.net_weight
                records.making_charge = records.product_id.making_charges_percentages or records.product_id.product_tmpl_id.making_charges_percentages
                records.product_stone_rate = records.product_id.stone_rate
                records.gold_weight = records.product_id.gold_weight or records.product_id.product_tmpl_id.gold_weight
                records.gold_waste = records.product_id.gold_waste or records.product_id.product_tmpl_id.gold_waste
                records.labour_charge = records.making_charge * records.product_weight

        return rec

    def _convert_to_tax_base_line_dict(self, **kwargs):
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
            taxes=self.tax_id,
            price_unit=self.price_unit,
            quantity=self.product_uom_qty,
            discount=self.discount,
            price_subtotal=self.price_subtotal,
            labour_charge=self.labour_charge,

            **kwargs,
        )

    
    @api.depends('product_weight')
    def calculate_total_weight(self):
        for line in self:
            line.product_weight = line.product_uom_qty * line.product_id.weight
            line.labour_charge = line.product_weight * line.making_charge
    

    @api.depends('product_uom_qty', 'discount', 'price_unit', 'tax_id','labour_charge')
    def _compute_amount(self):
        """
        Compute the amounts of the SO line.
        """
        for line in self:
            tax_results = self.env['account.tax']._compute_taxes([
                line._convert_to_tax_base_line_dict()
            ])
            totals = list(tax_results['totals'].values())[0]
            amount_untaxed = totals['amount_untaxed'] + line.labour_charge
            amount_tax = totals['amount_tax']

            line.update({
                'price_subtotal': amount_untaxed,
                'price_tax': amount_tax,
                'price_total': amount_untaxed + amount_tax,
            })

class AccountTax(models.Model):
    _inherit = 'account.tax'

    @api.model
    def _convert_to_tax_base_line_dict(
            self, base_line,
            partner=None, currency=None, product=None, taxes=None, price_unit=None, quantity=None,
            discount=None, account=None, analytic_distribution=None, price_subtotal=None,
            is_refund=False, rate=None,
            handle_price_include=True,
            extra_context=None,labour_charge = None,
    ):
        return {
            'record': base_line,
            'partner': partner or self.env['res.partner'],
            'currency': currency or self.env['res.currency'],
            'product': product or self.env['product.product'],
            'taxes': taxes or self.env['account.tax'],
            'price_unit': price_unit or 0.0,
            'quantity': quantity or 0.0,
            'discount': discount or 0.0,
            'account': account or self.env['account.account'],
            'analytic_distribution': analytic_distribution,
            'price_subtotal': price_subtotal or 0.0,
            'is_refund': is_refund,
            'rate': rate or 1.0,
            'handle_price_include': handle_price_include,
            'extra_context': extra_context or {},
            'labour_charge': labour_charge or 0.0 ,
        }

    @api.model
    def _prepare_tax_totals(self, base_lines, currency, tax_lines=None, is_company_currency_requested=False):
        """ Compute the tax totals details for the business documents.
        :param base_lines:                      A list of python dictionaries created using the '_convert_to_tax_base_line_dict' method.
        :param currency:                        The currency set on the business document.
        :param tax_lines:                       Optional list of python dictionaries created using the '_convert_to_tax_line_dict'
                                                method. If specified, the taxes will be recomputed using them instead of
                                                recomputing the taxes on the provided base lines.
        :param is_company_currency_requested :  Optional boolean which indicates whether or not the company currency is
                                                requested from the function. This can typically be used when using an
                                                invoice in foreign currency and the company currency is required.

        :return: A dictionary in the following form:
            {
                'amount_total':                 The total amount to be displayed on the document, including every total
                                                types.
                'amount_untaxed':               The untaxed amount to be displayed on the document.
                'formatted_amount_total':       Same as amount_total, but as a string formatted accordingly with
                                                partner's locale.
                'formatted_amount_untaxed':     Same as amount_untaxed, but as a string formatted accordingly with
                                                partner's locale.
                'groups_by_subtotals':          A dictionary formed liked {'subtotal': groups_data}
                                                Where total_type is a subtotal name defined on a tax group, or the
                                                default one: 'Untaxed Amount'.
                                                And groups_data is a list of dict in the following form:
                    {
                        'tax_group_name':                           The name of the tax groups this total is made for.
                        'tax_group_amount':                         The total tax amount in this tax group.
                        'tax_group_base_amount':                    The base amount for this tax group.
                        'formatted_tax_group_amount':               Same as tax_group_amount, but as a string formatted accordingly
                                                                    with partner's locale.
                        'formatted_tax_group_base_amount':          Same as tax_group_base_amount, but as a string formatted
                                                                    accordingly with partner's locale.
                        'tax_group_id':                             The id of the tax group corresponding to this dict.
                        'tax_group_base_amount_company_currency':   OPTIONAL: the base amount of the tax group expressed in
                                                                    the company currency when the parameter
                                                                    is_company_currency_requested is True
                        'tax_group_amount_company_currency':        OPTIONAL: the tax amount of the tax group expressed in
                                                                    the company currency when the parameter
                                                                    is_company_currency_requested is True
                    }
                'subtotals':                    A list of dictionaries in the following form, one for each subtotal in
                                                'groups_by_subtotals' keys.
                    {
                        'name':                             The name of the subtotal
                        'amount':                           The total amount for this subtotal, summing all the tax groups
                                                            belonging to preceding subtotals and the base amount
                        'formatted_amount':                 Same as amount, but as a string formatted accordingly with
                                                            partner's locale.
                        'amount_company_currency':          OPTIONAL: The total amount in company currency when the
                                                            parameter is_company_currency_requested is True
                    }
                'subtotals_order':              A list of keys of `groups_by_subtotals` defining the order in which it needs
                                                to be displayed
            }
        """

        # ==== Compute the taxes ====


        to_process = []
        for base_line in base_lines:
            to_update_vals, tax_values_list = self._compute_taxes_for_single_line(base_line)
            to_process.append((base_line, to_update_vals, tax_values_list))
            # print('**************CHECK********************************', base_line)
        labour_amount = 0

        for line in base_lines:
            if isinstance(line, dict):
                labour_amount += line.get('labour_charge', 0.0)
            # else:
            #     print(f"Skipping element {line} as it is not a dictionary.")

        # print("Total Labour Charge:", labour_amount)


        def grouping_key_generator(base_line, tax_values):
            source_tax = tax_values['tax_repartition_line'].tax_id
            return {'tax_group': source_tax.tax_group_id}


        global_tax_details = self._aggregate_taxes(to_process, grouping_key_generator=grouping_key_generator)

        tax_group_vals_list = []
        for tax_detail in global_tax_details['tax_details'].values():
            tax_group_vals = {
                'tax_group': tax_detail['tax_group'],
                'base_amount': tax_detail['base_amount_currency'],
                'tax_amount': tax_detail['tax_amount_currency'],
            }
            if is_company_currency_requested:
                tax_group_vals['base_amount_company_currency'] = tax_detail['base_amount']
                tax_group_vals['tax_amount_company_currency'] = tax_detail['tax_amount']

            # Handle a manual edition of tax lines.
            if tax_lines is not None:
                matched_tax_lines = [
                    x
                    for x in tax_lines
                    if x['tax_repartition_line'].tax_id.tax_group_id == tax_detail['tax_group']
                ]
                if matched_tax_lines:
                    tax_group_vals['tax_amount'] = sum(x['tax_amount'] for x in matched_tax_lines)

            tax_group_vals_list.append(tax_group_vals)

        tax_group_vals_list = sorted(tax_group_vals_list, key=lambda x: (x['tax_group'].sequence, x['tax_group'].id))

        # ==== Partition the tax group values by subtotals ====

        amount_untaxed = global_tax_details['base_amount_currency'] + labour_amount
        amount_tax = 0.0

        amount_untaxed_company_currency = global_tax_details['base_amount']
        amount_tax_company_currency = 0.0

        subtotal_order = {}
        groups_by_subtotal = defaultdict(list)
        for tax_group_vals in tax_group_vals_list:
            tax_group = tax_group_vals['tax_group']

            subtotal_title = tax_group.preceding_subtotal or _("Untaxed Amount")
            sequence = tax_group.sequence

            subtotal_order[subtotal_title] = min(subtotal_order.get(subtotal_title, float('inf')), sequence)
            groups_by_subtotal[subtotal_title].append({
                'group_key': tax_group.id,
                'tax_group_id': tax_group.id,
                'tax_group_name': tax_group.name,
                'tax_group_amount': tax_group_vals['tax_amount'],
                'tax_group_base_amount': tax_group_vals['base_amount'],
                'formatted_tax_group_amount': formatLang(self.env, tax_group_vals['tax_amount'], currency_obj=currency),
                'formatted_tax_group_base_amount': formatLang(self.env, tax_group_vals['base_amount'],
                                                              currency_obj=currency),
            })
            if is_company_currency_requested:
                groups_by_subtotal[subtotal_title][-1]['tax_group_amount_company_currency'] = tax_group_vals[
                    'tax_amount_company_currency']
                groups_by_subtotal[subtotal_title][-1]['tax_group_base_amount_company_currency'] = tax_group_vals[
                    'base_amount_company_currency']

        # ==== Build the final result ====

        subtotals = []
        for subtotal_title in sorted(subtotal_order.keys(), key=lambda k: subtotal_order[k]):
            amount_total = amount_untaxed + amount_tax
            subtotals.append({
                'name': subtotal_title,
                'amount': amount_total,
                'formatted_amount': formatLang(self.env, amount_total, currency_obj=currency),
            })
            if is_company_currency_requested:
                subtotals[-1]['amount_company_currency'] = amount_untaxed_company_currency + amount_tax_company_currency
                amount_tax_company_currency += sum(
                    x['tax_group_amount_company_currency'] for x in groups_by_subtotal[subtotal_title])

            amount_tax += sum(x['tax_group_amount'] for x in groups_by_subtotal[subtotal_title])

        amount_total = amount_untaxed + amount_tax

        # print('amount_totalamount_totalamount_total' , amount_total)

        display_tax_base = (len(global_tax_details['tax_details']) == 1 and currency.compare_amounts(
            tax_group_vals_list[0]['base_amount'], amount_untaxed) != 0) \
                           or len(global_tax_details['tax_details']) > 1

        return {
            'amount_untaxed': currency.round(amount_untaxed) if currency else amount_untaxed,
            'amount_total': currency.round(amount_total) if currency else amount_total,
            'formatted_amount_total': formatLang(self.env, amount_total, currency_obj=currency),
            'formatted_amount_untaxed': formatLang(self.env, amount_untaxed, currency_obj=currency),
            'groups_by_subtotal': groups_by_subtotal,
            'subtotals': subtotals,
            'subtotals_order': sorted(subtotal_order.keys(), key=lambda k: subtotal_order[k]),
            'display_tax_base': display_tax_base
        }



    





    
    
        

