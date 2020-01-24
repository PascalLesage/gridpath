#!/usr/bin/env python
# Copyright 2017 Blue Marble Analytics LLC. All rights reserved.

"""

This operational type describes a demand response (DR) project that can
shift load across timepoints, e.g. a building pre-cooling program or an
electric vehicle smart-charging program. There are two operational variables
in each timepoint: one for shifting load up (adding load) and another for
shifting load down (subtracting load). These cannot exceed the power capacity
of the project and must meet an energy balance constraint on each horizon.
Efficiency losses are not currently implemented.

"""

from pyomo.environ import Var, Set, Constraint, NonNegativeReals

from gridpath.auxiliary.auxiliary import generator_subset_init


def add_module_specific_components(m, d):
    """
    The following Pyomo model components are defined in this module:

    +-------------------------------------------------------------------------+
    | Sets                                                                    |
    +=========================================================================+
    | | :code:`DR`                                                            |
    |                                                                         |
    | The set of projects of the :code:`dr` operational type.                 |
    +-------------------------------------------------------------------------+
    | | :code:`DR_OPR_TMPS`                                                   |
    |                                                                         |
    | Two-dimensional set with projects of the :code:`dr`                     |
    | operational type and their operational timepoints.                      |
    +-------------------------------------------------------------------------+
    | | :code:`DR_OPR_HRZS`                                                   |
    |                                                                         |
    | Two-dimensional set with projects of the :code:`dr`                     |
    | operational type and their operational horizons.                        |
    +-------------------------------------------------------------------------+

    |

    +-------------------------------------------------------------------------+
    | Variables                                                               |
    +=========================================================================+
    | | :code:`DR_Shift_Up_MW`                                                |
    | | *Defined over*: :code:`DR_OPR_TMPS`                                   |
    | | *Within*: :code:`NonNegativeReals`                                    |
    |                                                                         |
    | Load added (in MW) in each operational timepoint.                       |
    +-------------------------------------------------------------------------+
    | | :code:`DR_Shift_Down_MW`                                              |
    | | *Defined over*: :code:`DR_OPR_TMPS`                                   |
    | | *Within*: :code:`NonNegativeReals`                                    |
    |                                                                         |
    | Load removed (in MW) in each operational timepoint.                     |
    +-------------------------------------------------------------------------+

    |

    +-------------------------------------------------------------------------+
    | Constraints                                                             |
    +=========================================================================+
    | | :code:`DR_Max_Shift_Up_Constraint`                                    |
    | | *Defined over*: :code:`DR_OPR_TMPS`                                   |
    |                                                                         |
    | Limits the added load to the available power capacity.                  |
    +-------------------------------------------------------------------------+
    | | :code:`DR_Max_Shift_Down_Constraint`                                  |
    | | *Defined over*: :code:`DR_OPR_TMPS`                                   |
    |                                                                         |
    | Limits the removed load to the available power capacity.                |
    +-------------------------------------------------------------------------+
    | | :code:`DR_Energy_Balance_Constraint`                                  |
    | | *Defined over*: :code:`DR_OPR_HRZS`                                   |
    |                                                                         |
    | Ensures no energy losses or gains when shifting load within the horizon.|
    +-------------------------------------------------------------------------+
    | | :code:`DR_Energy_Budget_Constraint`                                   |
    | | *Defined˚ over*: :code:`DR_OPR_HRZS`                                  |
    |                                                                         |
    | Total energy that can be shifted on each horizon should equal budget.   |
    +-------------------------------------------------------------------------+

    """

    # Sets
    ###########################################################################

    m.DR = Set(
        within=m.PROJECTS,
        initialize=generator_subset_init("operational_type", "dr")
    )

    m.DR_OPR_TMPS = Set(
        dimen=2, within=m.PROJECT_OPERATIONAL_TIMEPOINTS,
        rule=lambda mod:
        set((g, tmp) for (g, tmp) in mod.PROJECT_OPERATIONAL_TIMEPOINTS
            if g in mod.DR)
    )

    m.DR_OPR_HRZS = Set(
        dimen=2,
        rule=lambda mod:
        set((g, mod.horizon[tmp, mod.balancing_type_project[g]])
            for (g, tmp) in mod.PROJECT_OPERATIONAL_TIMEPOINTS
            if g in mod.DR)
    )

    # Variables
    ###########################################################################

    m.DR_Shift_Up_MW = Var(
        m.DR_OPR_TMPS,
        within=NonNegativeReals
    )

    m.DR_Shift_Down_MW = Var(
        m.DR_OPR_TMPS,
        within=NonNegativeReals
    )

    # Constraints
    ###########################################################################

    m.DR_Max_Shift_Up_Constraint = Constraint(
        m.DR_OPR_TMPS,
        rule=max_shift_up_rule
    )

    m.DR_Max_Shift_Down_Constraint = Constraint(
        m.DR_OPR_TMPS,
        rule=max_shift_down_rule
    )

    m.DR_Energy_Balance_Constraint = Constraint(
        m.DR_OPR_HRZS,
        rule=energy_balance_rule
    )

    m.DR_Energy_Budget_Constraint = Constraint(
        m.DR_OPR_HRZS,
        rule=energy_budget_rule
    )


# Constraint Formulation Rules
###############################################################################

def max_shift_up_rule(mod, p, tmp):
    """
    **Constraint Name**: DR_Max_Shift_Up_Constraint
    **Enforced Over**: DR_OPR_TMPS

    Limits the added load to the available power capacity.
    """
    return mod.DR_Shift_Up_MW[p, tmp] <= \
        mod.Capacity_MW[p, mod.period[tmp]]
    

def max_shift_down_rule(mod, p, tmp):
    """
    **Constraint Name**: DR_Max_Shift_Down_Constraint
    **Enforced Over**: DR_OPR_TMPS

    Limits the removed load to the available power capacity.
    """
    return mod.DR_Shift_Down_MW[p, tmp] <= \
        mod.Capacity_MW[p, mod.period[tmp]]


def energy_balance_rule(mod, p, h):
    """
    **Constraint Name**: DR_Energy_Balance_Constraint
    **Enforced Over**: DR_OPR_HRZS

    The sum of all shifted load up is equal to the sum of all shifted load
    down within an horizon, i.e. there are no energy losses or gains.
    """
    return sum(mod.DR_Shift_Up_MW[p, tmp]
               for tmp in mod.TIMEPOINTS_ON_HORIZON[h]) \
        == sum(mod.DR_Shift_Down_MW[p, tmp]
               for tmp in mod.TIMEPOINTS_ON_HORIZON[h])


def energy_budget_rule(mod, p, h):
    """
    **Constraint Name**: DR_Energy_Budget_Constraint
    **Enforced Over**: DR_OPR_HRZS

    Total energy that can be shifted on each horizon should equal budget.

    Get the period for the total capacity from the first timepoint of the
    horizon.
    """
    return sum(mod.DR_Shift_Up_MW[p, tmp]
               * mod.number_of_hours_in_timepoint[tmp]
               for tmp in mod.TIMEPOINTS_ON_HORIZON[h]) \
        == mod.Energy_Capacity_MWh[p, mod.period[
            mod.first_horizon_timepoint[h]]]


# Operational Type Methods
###############################################################################

def power_provision_rule(mod, p, tmp):
    """
    Provided power to the system is the load shifted down minus the load
    shifted up.
    """
    return mod.DR_Shift_Down_MW[p, tmp] - mod.DR_Shift_Up_MW[p, tmp]


def fuel_burn_rule(mod, p, tmp, error_message):
    """
    """
    if p in mod.FUEL_PROJECTS:
        raise ValueError(

            "ERROR! Shiftable load projects should not use fuel." + "\n" +
            "Check input data for project '{}'".format(p) + "\n" +
            "and change its fuel to '.' (no value)."
        )
    else:
        raise ValueError(error_message)


def startup_shutdown_rule(mod, p, tmp):
    """
    """
    raise ValueError(
        "ERROR! Shiftable load projects should not incur "
        "startup/shutdown costs." + "\n" +
        "Check input data for project '{}'".format(p) + "\n" +
        "and change its startup/shutdown costs to '.' (no value)."
    )


def power_delta_rule(mod, p, tmp):
    """
    """
    if tmp == mod.first_horizon_timepoint[
        mod.horizon[tmp, mod.balancing_type_project[p]]] \
            and mod.boundary[mod.horizon[tmp, mod.balancing_type_project[
            p]]] == "linear":
        pass
    else:
        return (mod.DR_Shift_Up_MW[p, tmp]
                - mod.DR_Shift_Down_MW[p, tmp]) - \
            (mod.DR_Shift_Up_MW[
                 p, mod.previous_timepoint[tmp, mod.balancing_type_project[p]]
             ]
                - mod.DR_Shift_Down_MW[
                 p, mod.previous_timepoint[tmp, mod.balancing_type_project[p]]
             ])
