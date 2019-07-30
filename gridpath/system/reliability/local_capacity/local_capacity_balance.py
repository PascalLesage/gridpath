#!/usr/bin/env python
# Copyright 2017 Blue Marble Analytics LLC. All rights reserved.

"""
Constraint total local capacity contribution to be more than or equal to the 
requirement.
"""
from __future__ import print_function

from builtins import next
import csv
import os.path

from pyomo.environ import Param, Var, Constraint, Expression, \
    NonNegativeReals, value

from gridpath.auxiliary.dynamic_components import \
    local_capacity_balance_provision_components


def add_model_components(m, d):
    """

    :param m:
    :param d:
    :return:
    """

    m.local_capacity_shortage_penalty_per_mw = \
        Param(m.LOCAL_CAPACITY_ZONES, within=NonNegativeReals)

    m.Local_Capacity_Shortage_MW = Var(
        m.LOCAL_CAPACITY_ZONE_PERIODS_WITH_REQUIREMENT,
        within=NonNegativeReals
    )

    m.Total_Local_Capacity_from_All_Sources_Expression_MW = Expression(
        m.LOCAL_CAPACITY_ZONE_PERIODS_WITH_REQUIREMENT,
        rule=lambda mod, z, p:
        sum(getattr(mod, component)[z, p] for component
            in getattr(d, local_capacity_balance_provision_components)
            )
    )

    def local_capacity_requirement_rule(mod, z, p):
        """
        Total local capacity provision must be greater than or equal to the
        requirement
        :param mod:
        :param z:
        :param p:
        :return:
        """
        return mod.Total_Local_Capacity_from_All_Sources_Expression_MW[z, p] \
            + mod.Local_Capacity_Shortage_MW[z, p] \
            >= mod.local_capacity_requirement_mw[z, p]

    m.Local_Capacity_Constraint = Constraint(
        m.LOCAL_CAPACITY_ZONE_PERIODS_WITH_REQUIREMENT,
        rule=local_capacity_requirement_rule
    )


def load_model_data(m, d, data_portal, scenario_directory, subproblem, stage):
    """

    :param m:
    :param d:
    :param data_portal:
    :param scenario_directory:
    :param subproblem:
    :param stage:
    :return:
    """
    data_portal.load(
        filename=os.path.join(
            scenario_directory, "inputs", "local_capacity_zones.tab"
        ),
        param=m.local_capacity_shortage_penalty_per_mw
    )


def export_results(scenario_directory, subproblem, stage, m, d):
    """

    :param scenario_directory:
    :param subproblem:
    :param stage:
    :param m:
    :param d:
    :return:
    """
    with open(os.path.join(scenario_directory, subproblem, stage, "results",
                           "local_capacity.csv"), "w") as rps_results_file:
        writer = csv.writer(rps_results_file)
        writer.writerow(["local_capacity_zone", "period",
                         "discount_factor", "number_years_represented",
                         "local_capacity_requirement_mw",
                         "local_capacity_provision_mw"])
        for (z, p) in m.LOCAL_CAPACITY_ZONE_PERIODS_WITH_REQUIREMENT:
            writer.writerow([
                z,
                p,
                m.discount_factor[p],
                m.number_years_represented[p],
                float(m.local_capacity_requirement_mw[z, p]),
                value(
                    m.Total_Local_Capacity_from_All_Sources_Expression_MW[z, p]
                )
            ])


def save_duals(m):
    m.constraint_indices["Local_Capacity_Constraint"] = \
        ["local_capacity_zone", "period", "dual"]


def import_results_into_database(scenario_id, subproblem, stage, c, db, results_directory):
    """

    :param scenario_id:
    :param c:
    :param db:
    :param results_directory:
    :return:
    """

    print("system local_capacity total")

    # Local capacity contribution
    c.execute(
        """UPDATE results_system_local_capacity
        SET local_capacity_requirement_mw = NULL,
        local_capacity_provision_mw = NULL
        WHERE scenario_id = {}
        AND subproblem_id = {}
        AND stage_id = {};
        """.format(scenario_id, subproblem, stage)
    )
    db.commit()

    with open(os.path.join(results_directory,
                           "local_capacity.csv"), "r") as \
            surface_file:
        reader = csv.reader(surface_file)

        next(reader)  # skip header
        for row in reader:
            local_capacity_zone = row[0]
            period = row[1]
            discount_factor = row[2]
            number_years = row[3]
            local_capacity_req_mw = row[4]
            local_capacity_prov_mw = row[5]

            c.execute(
                """UPDATE results_system_local_capacity
                SET local_capacity_requirement_mw = {},
                local_capacity_provision_mw = {},
                discount_factor = {},
                number_years_represented = {}
                WHERE scenario_id = {}
                AND local_capacity_zone = '{}'
                AND period = {}""".format(
                    local_capacity_req_mw, local_capacity_prov_mw,
                    discount_factor, number_years,
                    scenario_id, local_capacity_zone, period
                )
            )
    db.commit()

    # Update duals
    with open(os.path.join(results_directory, "Local_Capacity_Constraint.csv"),
              "r") as local_capacity_duals_file:
        reader = csv.reader(local_capacity_duals_file)

        next(reader)  # skip header

        for row in reader:
            c.execute(
                """UPDATE results_system_local_capacity
                SET dual = {}
                WHERE local_capacity_zone = '{}'
                AND period = {}
                AND scenario_id = {}
                AND subproblem_id = {}
                AND stage_id = {};""".format(
                    row[2], row[0], row[1], scenario_id, subproblem, stage
                )
            )
    db.commit()

    # Calculate marginal carbon cost per MMt
    c.execute(
        """UPDATE results_system_local_capacity
        SET local_capacity_marginal_cost_per_mw = 
        dual / (discount_factor * number_years_represented)
        WHERE scenario_id = {}
        AND subproblem_id = {}
        AND stage_id = {};
        """.format(scenario_id, subproblem, stage)
    )
    db.commit()