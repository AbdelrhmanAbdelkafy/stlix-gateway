"""ض.ق.م planner — how many purchase invoices this month still needs.

The owner's monthly routine, as a machine: sales are what the portal says we
issued; the target is to end up *paying* k‰ of sales (the group ≈ 8‰ = a 6%
gross margin × 14%); everything else is arithmetic — how much purchase VAT is
still missing, spread over the month's invoice slots (day 1 rule, weekly,
never the 30th), re-checked after month end for cancellations, then packed
for the return. See docs/vat-planner.md.
"""
