#!/usr/bin/env python
# Copyright 2017 Blue Marble Analytics LLC. All rights reserved.

"""
Zones where local capacity constraint is enforced; these can be different from
the load zones and other balancing areas.
"""

import csv
import os.path
from pyomo.environ import Set


def add_model_components(m, d):
    """

    :param m:
    :param d:
    :return:
    """

    m.LOCAL_CAPACITY_ZONES = Set()


def load_model_data(m, d, data_portal, scenario_directory, horizon, stage):
    """

    :param m:
    :param d:
    :param data_portal:
    :param scenario_directory:
    :param horizon:
    :param stage:
    :return:
    """
    data_portal.load(filename=os.path.join(scenario_directory, horizon, stage,
                                           "inputs",
                                           "local_capacity_zones.tab"),
                     select=("local_capacity_zone",),
                     index=m.LOCAL_CAPACITY_ZONES,
                     param=()
                     )


def get_inputs_from_database(subscenarios, c, inputs_directory):
    """
    local_capacity_zones.tab
    :param subscenarios
    :param c:
    :param inputs_directory:
    :return:
    """
    with open(os.path.join(inputs_directory,
                           "local_capacity_zones.tab"), "w") as \
            local_capacity_zones_file:
        writer = csv.writer(local_capacity_zones_file, delimiter="\t")

        # Write header
        writer.writerow(
            ["local_capacity_zone", "local_capacity_shortage_penalty_per_mw"]
        )

        local_capacity_zones = c.execute(
            """SELECT local_capacity_zone, 
            local_capacity_shortage_penalty_per_mw
            FROM inputs_geography_local_capacity_zones
            WHERE local_capacity_zone_scenario_id = {};
            """.format(
                subscenarios.LOCAL_CAPACITY_ZONE_SCENARIO_ID
            )
        )
        for row in local_capacity_zones:
            writer.writerow([row[0], row[1]])
