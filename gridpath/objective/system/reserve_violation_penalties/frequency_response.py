#!/usr/bin/env python
# Copyright 2017 Blue Marble Analytics LLC. All rights reserved.

from pyomo.environ import Expression

from gridpath.auxiliary.dynamic_components import total_cost_components
from aggregate_reserve_violation_penalties import \
    generic_add_model_components, generic_load_model_data


def add_model_components(m, d):
    """

    :param m:
    :param d:
    :return:
    """

    # Total freq response requirement
    generic_add_model_components(
        m,
        d,
        "FREQUENCY_RESPONSE_BAS",
        "FREQUENCY_RESPONSE_BA_TIMEPOINTS",
        "Frequency_Response_Violation_MW",
        "frequency_response_violation_penalty_per_mw",
        "Frequency_Response_Penalty_Costs"
        )

    # Partial frequency response requirement

    # Add violation penalty costs incurred to objective function
    # Assume violation cost is the same as for the total requirement
    def partial_frequency_response_penalty_costs_rule(mod):
        return sum(mod.Frequency_Response_Partial_Violation_MW[ba, tmp]
                   * mod.frequency_response_violation_penalty_per_mw[ba]
                   * mod.number_of_hours_in_timepoint[tmp]
                   * mod.horizon_weight[mod.horizon[tmp]]
                   * mod.number_years_represented[mod.period[tmp]]
                   * mod.discount_factor[mod.period[tmp]]
                   for (ba, tmp)
                   in mod.FREQUENCY_RESPONSE_BA_TIMEPOINTS
                   )
    m.Frequency_Response_Partial_Penalty_Costs = \
        Expression(rule=partial_frequency_response_penalty_costs_rule)

    getattr(d, total_cost_components).append(
        "Frequency_Response_Partial_Penalty_Costs")


def load_model_data(m, d, data_portal, scenario_directory, horizon, stage):
    generic_load_model_data(m, d, data_portal,
                            scenario_directory, horizon, stage,
                            "load_following_up_balancing_areas.tab",
                            "frequency_response_violation_penalty_per_mw"
                            )