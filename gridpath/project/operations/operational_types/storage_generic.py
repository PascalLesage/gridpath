#!/usr/bin/env python
# Copyright 2017 Blue Marble Analytics LLC. All rights reserved.

"""
Operations of generic storage
"""

import csv
import os.path
from pandas import read_csv
from pyomo.environ import Var, Set, Constraint, Param, NonNegativeReals, \
    PercentFraction, value

from gridpath.auxiliary.auxiliary import generator_subset_init
from gridpath.auxiliary.dynamic_components import headroom_variables, \
    footroom_variables


def add_module_specific_components(m, d):
    """
    Add a capacity commit variable to represent the amount of capacity that is
    on.
    :param m:
    :return:
    """
    # Sets and params
    m.STORAGE_GENERIC_PROJECTS = Set(
        within=m.PROJECTS,
        initialize=
        generator_subset_init("operational_type",
                              "storage_generic")
    )

    m.STORAGE_GENERIC_PROJECT_OPERATIONAL_TIMEPOINTS = \
        Set(dimen=2,
            rule=lambda mod:
            set((g, tmp) for (g, tmp) in mod.PROJECT_OPERATIONAL_TIMEPOINTS
                if g in mod.STORAGE_GENERIC_PROJECTS))

    m.storage_generic_charging_efficiency = \
        Param(m.STORAGE_GENERIC_PROJECTS, within=PercentFraction)
    m.storage_generic_discharging_efficiency = \
        Param(m.STORAGE_GENERIC_PROJECTS, within=PercentFraction)

    # Variables
    m.Generic_Storage_Discharge_MW = \
        Var(m.STORAGE_GENERIC_PROJECT_OPERATIONAL_TIMEPOINTS,
            within=NonNegativeReals)
    m.Generic_Storage_Charge_MW = \
        Var(m.STORAGE_GENERIC_PROJECT_OPERATIONAL_TIMEPOINTS,
            within=NonNegativeReals
            )
    m.Starting_Energy_in_Generic_Storage_MWh = \
        Var(m.STORAGE_GENERIC_PROJECT_OPERATIONAL_TIMEPOINTS,
            within=NonNegativeReals
            )

    # Operational constraints
    def max_discharge_rule(mod, s, tmp):
        """

        :param mod:
        :param s:
        :param tmp:
        :return:
        """
        return mod.Generic_Storage_Discharge_MW[s, tmp] \
            <= mod.Capacity_MW[s, mod.period[tmp]]

    m.Storage_Max_Discharge_Constraint = \
        Constraint(
            m.STORAGE_GENERIC_PROJECT_OPERATIONAL_TIMEPOINTS,
            rule=max_discharge_rule
        )

    def max_charge_rule(mod, s, tmp):
        """

        :param mod:
        :param s:
        :param tmp:
        :return:
        """
        return mod.Generic_Storage_Charge_MW[s, tmp] \
            <= mod.Capacity_MW[s, mod.period[tmp]]

    m.Storage_Generic_Max_Charge_Constraint = \
        Constraint(
            m.STORAGE_GENERIC_PROJECT_OPERATIONAL_TIMEPOINTS,
            rule=max_charge_rule
        )

    # For reserves, we can also look at the additional headroom available
    # when charging; not charging also counts as footroom
    def max_headroom_power_rule(mod, s, tmp):
        """

        :param mod:
        :param s:
        :param tmp:
        :return:
        """
        return sum(getattr(mod, c)[s, tmp]
                   for c in getattr(d, headroom_variables)[s]) \
            <= \
            mod.Capacity_MW[s, mod.period[tmp]] \
            - mod.Generic_Storage_Discharge_MW[s, tmp] \
            + mod.Generic_Storage_Charge_MW[s, tmp]

    m.Storage_Generic_Max_Headroom_Power_Constraint = \
        Constraint(
            m.STORAGE_GENERIC_PROJECT_OPERATIONAL_TIMEPOINTS,
            rule=max_headroom_power_rule
        )

    def max_footroom_power_rule(mod, s, tmp):
        """

        :param mod:
        :param s:
        :param tmp:
        :return:
        """
        return sum(getattr(mod, c)[s, tmp]
                   for c in getattr(d, footroom_variables)[s]) \
            <= mod.Generic_Storage_Discharge_MW[s, tmp] \
            + mod.Capacity_MW[s, mod.period[tmp]] \
            - mod.Generic_Storage_Charge_MW[s, tmp]

    m.Storage_Generic_Max_Footroom_Power_Constraint = \
        Constraint(
            m.STORAGE_GENERIC_PROJECT_OPERATIONAL_TIMEPOINTS,
            rule=max_footroom_power_rule
        )

    # Headroom and footroom energy constraints
    # TODO: allow different sustained duration requirements; assumption here is
    # that if reserves are called, new setpoint must be sustained for 1 hour
    # TODO: allow derate of the net energy in the current timepoint in the
    # headroom and footroom energy rules; in reality, reserves could be
    # called at the very beginning or the very end of the timepoint (e.g. hour)
    # If called at the end, we would have all the net energy (or
    # resulting 'room in the tank') available, but if called in the beginning
    # none of it would be available

    # Can't provide more reserves (times sustained duration required) than
    # available energy in storage (for upward reserves) in that timepoint or
    # available capacity to store energy (for downward reserves) in that
    # timepoint
    def max_headroom_energy_rule(mod, s, tmp):
        """
        How much energy do we have available
        :param mod:
        :param s:
        :param tmp:
        :return:
        """
        return sum(getattr(mod, c)[s, tmp]
                   for c in getattr(d, headroom_variables)[s]) \
            * mod.number_of_hours_in_timepoint[tmp] \
            / mod.storage_generic_discharging_efficiency[s] \
            <= \
            mod.Starting_Energy_in_Generic_Storage_MWh[s, tmp] \
            + mod.Generic_Storage_Charge_MW[s, tmp] \
            * mod.number_of_hours_in_timepoint[tmp] \
            * mod.storage_generic_charging_efficiency[s] \
            - mod.Generic_Storage_Discharge_MW[s, tmp] \
            * mod.number_of_hours_in_timepoint[tmp]  \
            / mod.storage_generic_discharging_efficiency[s]

    m.Storage_Generic_Max_Headroom_Energy_Constraint = \
        Constraint(
            m.STORAGE_GENERIC_PROJECT_OPERATIONAL_TIMEPOINTS,
            rule=max_headroom_energy_rule
        )

    def max_footroom_energy_rule(mod, s, tmp):
        """
        How much room is left in the tank
        :param mod:
        :param s:
        :param tmp:
        :return:
        """
        return sum(getattr(mod, c)[s, tmp]
                   for c in getattr(d, headroom_variables)[s]) \
            * mod.number_of_hours_in_timepoint[tmp] \
            * mod.storage_generic_charging_efficiency[s] \
            <= \
            mod.Capacity_MW[s, mod.period[tmp]] - \
            mod.Starting_Energy_in_Generic_Storage_MWh[s, tmp] \
            - mod.Generic_Storage_Charge_MW[s, tmp] \
            * mod.number_of_hours_in_timepoint[tmp] \
            * mod.storage_generic_charging_efficiency[s] \
            + mod.Generic_Storage_Discharge_MW[s, tmp] \
            * mod.number_of_hours_in_timepoint[tmp] \
            / mod.storage_generic_discharging_efficiency[s]

    m.Storage_Generic_Max_Footroom_Energy_Constraint = \
        Constraint(
            m.STORAGE_GENERIC_PROJECT_OPERATIONAL_TIMEPOINTS,
            rule=max_footroom_energy_rule
        )

    # TODO: adjust storage energy for reserves provided
    def energy_tracking_rule(mod, s, tmp):
        """

        :param mod:
        :param g:
        :param tmp:
        :return:
        """
        if tmp == mod.first_horizon_timepoint[mod.horizon[tmp]] \
                and mod.boundary[mod.horizon[tmp]] == "linear":
            return Constraint.Skip
        else:
            return \
                mod.Starting_Energy_in_Generic_Storage_MWh[s, tmp] \
                == mod.Starting_Energy_in_Generic_Storage_MWh[
                    s, mod.previous_timepoint[tmp]] \
                + mod.Generic_Storage_Charge_MW[
                      s, mod.previous_timepoint[tmp]] \
                * mod.number_of_hours_in_timepoint[
                      mod.previous_timepoint[tmp]] \
                * mod.storage_generic_charging_efficiency[s] \
                - mod.Generic_Storage_Discharge_MW[
                      s, mod.previous_timepoint[tmp]] \
                * mod.number_of_hours_in_timepoint[
                      mod.previous_timepoint[tmp]] \
                / mod.storage_generic_discharging_efficiency[s]

    m.Storage_Generic_Energy_Tracking_Constraint = \
        Constraint(m.STORAGE_GENERIC_PROJECT_OPERATIONAL_TIMEPOINTS,
                   rule=energy_tracking_rule)

    def max_energy_in_storage_rule(mod, s, tmp):
        """

        :param mod:
        :param s:
        :param tmp:
        :return:
        """
        return mod.Starting_Energy_in_Generic_Storage_MWh[s, tmp] \
            <= mod.Energy_Capacity_MWh[s, mod.period[tmp]]
    m.Max_Energy_in_Generic_Storage_Constraint = \
        Constraint(m.STORAGE_GENERIC_PROJECT_OPERATIONAL_TIMEPOINTS,
                   rule=max_energy_in_storage_rule)


def power_provision_rule(mod, s, tmp):
    """
    Power provision from storage
    :param mod:
    :param s:
    :param tmp:
    :return:
    """
    return mod.Generic_Storage_Discharge_MW[s, tmp] \
        - mod.Generic_Storage_Charge_MW[s, tmp]


def scheduled_curtailment_rule(mod, g, tmp):
    """
    Curtailment not allowed
    :param mod:
    :param g:
    :param tmp:
    :return:
    """
    return 0


# TODO: ignoring subhourly behavior for storage for now
def subhourly_curtailment_rule(mod, g, tmp):
    """
    Can't provide reserves
    :param mod:
    :param g:
    :param tmp:
    :return:
    """
    return 0


def subhourly_energy_delivered_rule(mod, g, tmp):
    """
    Can't provide reserves
    :param mod:
    :param g:
    :param tmp:
    :return:
    """
    return 0


def fuel_cost_rule(mod, g, tmp):
    """

    :param mod:
    :param g:
    :param tmp:
    :return:
    """
    return 0


def startup_rule(mod, g, tmp):
    """

    :param mod:
    :param g:
    :param tmp:
    :return:
    """
    return 0


def shutdown_rule(mod, g, tmp):
    """

    :param mod:
    :param g:
    :param tmp:
    :return:
    """
    return 0


def load_module_specific_data(mod, data_portal, scenario_directory,
                              horizon, stage):
    """

    :param mod:
    :param data_portal:
    :param scenario_directory:
    :param horizon:
    :param stage:
    :return:
    """
    def determine_efficiencies():
        """

        :param mod:
        :return:
        """
        storage_generic_charging_efficiency = dict()
        storage_generic_discharging_efficiency = dict()

        dynamic_components = \
            read_csv(
                os.path.join(scenario_directory, "inputs", "projects.tab"),
                sep="\t", usecols=["project", "operational_type",
                                   "charging_efficiency",
                                   "discharging_efficiency"]
            )
        for row in zip(dynamic_components["project"],
                       dynamic_components["operational_type"],
                       dynamic_components["charging_efficiency"],
                       dynamic_components["discharging_efficiency"]):
            if row[1] == "storage_generic":
                storage_generic_charging_efficiency[row[0]] \
                    = float(row[2])
                storage_generic_discharging_efficiency[row[0]] \
                    = float(row[3])
            else:
                pass

        return storage_generic_charging_efficiency, \
               storage_generic_discharging_efficiency

    data_portal.data()["storage_generic_charging_efficiency"] = \
        determine_efficiencies()[0]
    data_portal.data()["storage_generic_discharging_efficiency"] = \
        determine_efficiencies()[1]


def export_module_specific_results(mod, d, scenario_directory, horizon, stage):
    """

    :param scenario_directory:
    :param horizon:
    :param stage:
    :param mod:
    :param d:
    :return:
    """
    with open(os.path.join(scenario_directory, horizon, stage, "results",
                           "dispatch_storage_generic.csv"), "wb") as f:
        writer = csv.writer(f)
        writer.writerow(["project", "period", "horizon", "timepoint",
                         "horizon_weight", "number_of_hours_in_timepoint",
                         "starting_energy_mwh",
                         "charge_mw", "discharge_mw"])
        for (p, tmp) in mod.STORAGE_GENERIC_PROJECT_OPERATIONAL_TIMEPOINTS:
            writer.writerow([
                p,
                mod.period[tmp],
                mod.horizon[tmp],
                tmp,
                mod.horizon_weight[mod.horizon[tmp]],
                mod.number_of_hours_in_timepoint[tmp],
                value(mod.Starting_Energy_in_Generic_Storage_MWh[p, tmp]),
                value(mod.Generic_Storage_Charge_MW[p, tmp]),
                value(mod.Generic_Storage_Discharge_MW[p, tmp])
            ])