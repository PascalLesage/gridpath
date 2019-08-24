#!/usr/bin/env python
# Copyright 2017 Blue Marble Analytics LLC. All rights reserved.

"""
Make plot of capacity by period and technology for a certain zone/stage
"""

from argparse import ArgumentParser
from bokeh.models import ColumnDataSource, Legend, NumeralTickFormatter
from bokeh.plotting import figure
from bokeh.models.tools import HoverTool
from bokeh.embed import json_item
from bokeh.palettes import cividis

import pandas as pd
import sys

# GridPath modules
from viz.common_functions import connect_to_database, show_hide_legend, \
    show_plot, get_scenario_and_scenario_id


def parse_arguments(arguments):
    """

    :return:
    """
    parser = ArgumentParser(add_help=True)

    # Scenario name and location options
    parser.add_argument("--database",
                        help="The database file path. Defaults to ../db/io.db "
                             "if not specified")
    parser.add_argument("--scenario_id", help="The scenario ID. Required if "
                                              "no --scenario is specified.")
    parser.add_argument("--scenario", help="The scenario name. Required if "
                                           "no --scenario_id is specified.")
    parser.add_argument("--scenario_location",
                        help="The path to the directory in which to create "
                             "the scenario directory. Defaults to "
                             "'../scenarios' if not specified.")
    parser.add_argument("--load_zone",
                        help="The name of the load zone. Required.")
    parser.add_argument("--capacity_type", default="new",
                        help="The type of capacity to plot. 'new', 'all', "
                             "'retired'. Defaults to 'new'")
    parser.add_argument("--ylimit", help="Set y-axis limit.", type=float)
    parser.add_argument("--show",
                        default=False, action="store_true",
                        help="Show and save figure to "
                             "results/figures directory "
                             "under scenario directory.")
    parser.add_argument("--return_json",
                        default=False, action="store_true",
                        help="Return plot as a json file."
                        )
    # Parse arguments
    parsed_arguments = parser.parse_known_args(args=arguments)[0]

    return parsed_arguments


def get_capacity(c, scenario_id, load_zone, capacity_type):
    """
    Get capacity results. Can be new build, existing, or retired capacity
    :param c:
    :param scenario_id:
    :param load_zone:
    :param capacity_type:
    :return:
    """

    # TODO: add existing only? (all - new)
    # TODO: double check that "all" is net of retirements

    # Capacity by period and technology
    if capacity_type == "new":
        sql = """SELECT period, technology, sum(new_build_mw) as capacity_mw
            FROM results_project_capacity_new_build_generator
            WHERE scenario_id = ?
            AND load_zone = ?
            GROUP BY period, technology
            UNION
            SELECT period, technology, sum(new_build_mw) as mw
            FROM results_project_capacity_new_build_generator
            WHERE scenario_id = ?
            AND load_zone = ?
            GROUP BY period, technology;"""
        capacity = c.execute(sql, (scenario_id, load_zone,
                                   scenario_id, load_zone))
    elif capacity_type == "all":
        sql = """SELECT period, technology, sum(capacity_mw) as capacity_mw
            FROM results_project_capacity_all
            WHERE scenario_id = ?
            AND load_zone = ?
            GROUP BY period, technology;"""
        capacity = c.execute(sql, (scenario_id, load_zone))
    elif capacity_type == "retired":
        sql = """SELECT period, technology, sum(retired_mw) as capacity_mw
            FROM (SELECT scenario_id, load_zone, project, period, technology, 
                  retired_mw 
                  FROM results_project_capacity_linear_economic_retirement
                  UNION 
                  SELECT scenario_id, load_zone, project, period, technology, 
                  retired_mw 
                  FROM results_project_capacity_binary_economic_retirement
                 ) as tbl
            WHERE scenario_id = ?
            AND load_zone = ?
            GROUP BY period, technology;"""
        capacity = c.execute(sql, (scenario_id, load_zone))
    else:
        raise ValueError("Invalid capacity_type provided. Valid options are: "
                         "'new', 'all', or 'retired'. Default is 'new'")

    return capacity


def create_data_df(c, scenario_id, load_zone, capacity_type):
    """
    Get capacity results and pivot into data df
    :param c:
    :param scenario_id:
    :param load_zone:
    :param capacity_type:
    :return:
    """

    capacity = get_capacity(c, scenario_id, load_zone, capacity_type)

    df = pd.DataFrame(
        data=capacity.fetchall(),
        columns=[n[0] for n in capacity.description]
    )

    df = df.pivot(
        index='period',
        columns='technology',
        values='capacity_mw'
    )

    # Change index type from int to string (required for categorical bar chart)
    df.index = df.index.map(str)

    # For Testing:
    # df = pd.DataFrame(
    #     index=["2018", "2020"],
    #     data=[[0, 3000, 500, 1500],
    #           [0, 6000, 4500, 2300]],
    #     columns=["Biomass", "Hydro", "Solar", "Wind"]
    # )
    # df.index.name = "period"

    return df


def create_plot(df, title, ylimit=None):
    """

    :param df:
    :param title: string, plot title
    :param ylimit: float/int, upper limit of y-axis; optional
    :return:
    """

    # TODO: handle empty dataframe (will give bokeh warning)

    # Set up data source
    source = ColumnDataSource(data=df)

    # Determine column types for plotting, legend and colors
    # Order of stacked_cols will define order of stacked areas in chart
    stacked_cols = list(df.columns)

    # Stacked Area Colors
    colors = cividis(len(stacked_cols))

    # Set up the figure
    plot = figure(
        plot_width=800, plot_height=500,
        tools=["pan", "reset", "zoom_in", "zoom_out", "save", "help"],
        title=title,
        x_range=df.index.values
        # sizing_mode="scale_both"
    )

    # Add stacked area chart to plot
    area_renderers = plot.vbar_stack(
        stackers=stacked_cols,
        x="period",
        source=source,
        color=colors,
        width=0.5,
    )

    # Keep track of legend items
    legend_items = [(y, [area_renderers[i]]) for i, y in enumerate(stacked_cols)
                    if df[y].mean() > 0]

    # Add Legend
    legend = Legend(items=legend_items)
    plot.add_layout(legend, 'right')
    plot.legend[0].items.reverse()  # Reverse legend to match stacked order
    plot.legend.click_policy = 'hide'  # Add interactivity to the legend
    # Note: Doesn't rescale the graph down, simply hides the area
    # Note2: There's currently no way to auto-size legend based on graph size(?)
    # except for maybe changing font size automatically?
    show_hide_legend(plot=plot)  # Hide legend on double click

    # Format Axes (labels, number formatting, range, etc.)
    plot.xaxis.axis_label = "Period"
    plot.yaxis.axis_label = "Capacity (MW)"
    plot.yaxis.formatter = NumeralTickFormatter(format="0,0")
    plot.y_range.end = ylimit  # will be ignored if ylimit is None

    # Add HoverTools for stacked bars/areas
    for r in area_renderers:
        technology = r.name
        hover = HoverTool(
            tooltips=[
                ("Period", "@period"),
                ("Technology", technology),
                ("Capacity", "@%s{0,0} MW" % technology)
            ],
            renderers=[r],
            toggleable=False)
        plot.add_tools(hover)

    return plot


def main(args=None):
    """
    Parse the arguments, get the data in a df, and create the plot

    :return: if requested, return the plot as JSON object
    """
    if args is None:
        args = sys.argv[1:]
    parsed_args = parse_arguments(arguments=args)

    db = connect_to_database(parsed_arguments=parsed_args)
    c = db.cursor()

    scenario_location = parsed_args.scenario_location
    scenario, scenario_id = get_scenario_and_scenario_id(
        parsed_arguments=parsed_args,
        c=c
    )

    plot_title = "{} Capacity by Period - {}".format(
        parsed_args.capacity_type.capitalize(), parsed_args.load_zone
    )
    # TODO: add capacity type to title?
    plot_name = "{}CapacityPlot-{}".format(
        parsed_args.capacity_type, parsed_args.load_zone)

    df = create_data_df(
        c=c,
        scenario_id=scenario_id,
        load_zone=parsed_args.load_zone,
        capacity_type=parsed_args.capacity_type
    )

    plot = create_plot(
        df=df,
        title=plot_title,
        ylimit=parsed_args.ylimit
    )

    # Show plot in HTML browser file if requested
    if parsed_args.show:
        show_plot(scenario_directory=scenario_location,
                  scenario=scenario,
                  plot=plot,
                  plot_name=plot_name)

    # Return plot in json format if requested
    if parsed_args.return_json:
        return json_item(plot, plot_name)


if __name__ == "__main__":
    main()
