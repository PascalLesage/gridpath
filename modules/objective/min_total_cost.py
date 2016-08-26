#!/usr/bin/env python

from pyomo.environ import Expression, Objective, minimize


def add_model_components(m, d):
    """
    Aggregate costs and components to objective function.
    :param m:
    :param d:
    :return:
    """

    def penalty_costs_rule(mod):
        return sum((mod.Unserved_Energy_MW[z, tmp]
                    * mod.unserved_energy_penalty_per_mw +
                    mod.Overgeneration_MW[z, tmp]
                    * mod.overgeneration_penalty_per_mw)
                   for z in mod.LOAD_ZONES for tmp in mod.TIMEPOINTS)
    m.Penalty_Costs = Expression(rule=penalty_costs_rule)
    d.total_cost_components.append("Penalty_Costs")

    # Power production variable costs
    # TODO: fix this when periods added, etc.
    def total_generation_cost_rule(m):
        """
        Power production cost for all generators across all timepoints
        :param m:
        :return:
        """
        return sum(m.Generation_Cost[g, tmp]
                   for g in m.GENERATORS
                   for tmp in m.TIMEPOINTS)

    m.Total_Generation_Cost = Expression(rule=total_generation_cost_rule)
    d.total_cost_components.append("Total_Generation_Cost")

    # Startup and shutdown costs
    def total_startup_cost_rule(mod):
        """
        Sum startup costs for the objective function term.
        :param mod:
        :return:
        """
        return sum(mod.Startup_Cost[g, tmp]
                   for g in mod.STARTUP_COST_GENERATORS
                   for tmp in mod.TIMEPOINTS)
    m.Total_Startup_Cost = Expression(rule=total_startup_cost_rule)
    d.total_cost_components.append("Total_Startup_Cost")

    def total_shutdown_cost_rule(mod):
        """
        Sum shutdown costs for the objective function term.
        :param mod:
        :return:
        """
        return sum(mod.Shutdown_Cost[g, tmp]
                   for g in mod.SHUTDOWN_COST_GENERATORS
                   for tmp in mod.TIMEPOINTS)
    m.Total_Shutdown_Cost = Expression(rule=total_shutdown_cost_rule)
    d.total_cost_components.append("Total_Shutdown_Cost")

    # Define objective function
    def total_cost_rule(mod):

        return sum(getattr(mod, c)
                   for c in d.total_cost_components)

    m.Total_Cost = Objective(rule=total_cost_rule, sense=minimize)