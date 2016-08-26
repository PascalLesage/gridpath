#!/usr/bin/env python

import os.path
from pyomo.environ import Set, Param, NonNegativeReals


def add_model_components(m, d):
    m.GENERATORS = Set()

    m.capacity_mw = Param(m.GENERATORS, within=NonNegativeReals)
    m.variable_cost_per_mwh = Param(m.GENERATORS, within=NonNegativeReals)


def load_model_data(m, data_portal, scenario_directory, horizon, stage):
    data_portal.load(filename=os.path.join(scenario_directory,
                                           "inputs", "generators.tab"),
                     index=m.GENERATORS,
                     select=("GENERATORS", "capacity_mw",
                             "variable_cost_per_mwh"),
                     param=(m.capacity_mw, m.variable_cost_per_mwh)
                     )


def view_loaded_data(instance):
    print "Viewing data"
    for g in instance.GENERATORS:
        print(g, instance.capacity[g])