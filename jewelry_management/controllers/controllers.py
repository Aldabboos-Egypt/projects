# -*- coding: utf-8 -*-
# from odoo import http


# class PragtechJewelryMangement(http.Controller):
#     @http.route('/pragtech_jewelry_mangement/pragtech_jewelry_mangement', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/pragtech_jewelry_mangement/pragtech_jewelry_mangement/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('pragtech_jewelry_mangement.listing', {
#             'root': '/pragtech_jewelry_mangement/pragtech_jewelry_mangement',
#             'objects': http.request.env['pragtech_jewelry_mangement.pragtech_jewelry_mangement'].search([]),
#         })

#     @http.route('/pragtech_jewelry_mangement/pragtech_jewelry_mangement/objects/<model("pragtech_jewelry_mangement.pragtech_jewelry_mangement"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('pragtech_jewelry_mangement.object', {
#             'object': obj
#         })

