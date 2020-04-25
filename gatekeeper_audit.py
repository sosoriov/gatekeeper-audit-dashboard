#!/usr/local/bin/python3
from kubernetes import client, config
import dash
import dash_table
from dash.dependencies import Input, Output
import dash_core_components as dcc
import dash_html_components as html
import pandas as pd
import json
import kubernetes.client
from kubernetes.client.rest import ApiException
import urllib3
import flask
import os
urllib3.disable_warnings(urllib3.exceptions.SecurityWarning)

server = flask.Flask(__name__)
app = dash.Dash(__name__, server=server)

df, df_details = None, None
dataset = { "name": {}, "violations": {}, "id": {}}
group = 'constraints.gatekeeper.sh'
version = 'v1beta1'  

def get_gatekeeper_rules():
  server.config.from_pyfile('config/config.cfg')

  rules = server.config.get('RULES')
  gatekeper_list = []
  if rules is not None:
    rules_list = rules.split(',')

    gatekeper_list = [rule.strip() for rule in rules_list]
  
  return gatekeper_list


def k8s_auth():
  if os.environ.get('ENVIRONMENT') is None or os.environ.get('ENVIRONMENT') == 'local':
    config.load_kube_config()
  else:
    # authenticathe via ServiceAccount
    config.load_incluster_config()

  return kubernetes.client.CustomObjectsApi(kubernetes.client.ApiClient())


gatekeeper_templates = get_gatekeeper_rules()


def get_constraints_data(api_instance):
  details = []
  for gatekeeper_template in gatekeeper_templates:
    try:
      api_response = api_instance.list_cluster_custom_object(group, version, gatekeeper_template)
    except ApiException as e:
      print("Exception when calling CustomObjectsApi->get_cluster_custom_object: %s\n" % e)
      continue

    for item in api_response.get('items'):
      uid = item.get('metadata').get('uid')
      name = item.get('metadata').get('name')
      status = item.get('status')

      dataset["id"][uid] = uid
      dataset["name"][uid] = name
      dataset["violations"][uid] = status.get('totalViolations')

      if not status.get('violations'):
        continue

      violation_ids = []
      for violation in status.get('violations'):
        v_ids = "{}-{}-{}-{}".format(uid, violation.get('name'), violation.get('namespace'), violation.get('kind'))
        if v_ids in violation_ids:
          continue
        
        violation_ids.append(v_ids)
        
        detail = {"name": violation.get('name'), "namespace":  violation.get('namespace'),
                  "message": violation.get('message'), "kind": violation.get('kind'),
                  "enforcementAction": violation.get('enforcementAction'), "uid": uid}
          
        details.append(detail)
  return json.dumps(dataset), json.dumps(details)

api_instance = k8s_auth()

def get_k8s_data():
  global df
  global df_details
  # get table data:
  k8s_dataset, rule_detail = get_constraints_data(api_instance)
  try:
    df = pd.read_json(k8s_dataset)
  except Exception as err:
    print("An error ocurred reading K8s api: %s\n" % err)

  try:
    df_details = pd.read_json(rule_detail)
  except Exception as err:
    print("An error ocurred reading details from K8s api: %s\n" % err)
  
  return df, df_details


def description_card():
    """
    :return: A Div containing dashboard title & descriptions.
    """
    return html.Div(
        id="description-card",
        children=[
            html.H3("Gatekeeper Audit Dashboard"),
            html.H5("Meet governance and legal requirements"),
            html.Div(
                id="intro",
                children="Explore possible violations in your cluster in an easy way.",
            ),
        ],
    )

def summary_violations():
  """
  :return: A Dash table containing total number of violations.
  """
  return dash_table.DataTable(
          id='table-violations',
          columns=[{"name": i, "id": i } for i in df.columns if i != 'id'],
          data=df.to_dict('records'),
          sort_action="native",
          sort_mode='multi',
          sort_by=[{'column_id': 'violations', 'direction': 'desc'}],
          filter_action="native",
          style_cell={'padding': '5px', 'textAlign': 'left', 'font-size': '16px'},    
          style_as_list_view=True,
          style_header={
              'backgroundColor': '#e6e8e6',
              'fontWeight': 'bold'
          },
          style_data_conditional=[
            {
              'if': {
                  'column_id': 'violations',
                  'filter_query': '{violations} > 0'
              },
              'backgroundColor': '#cdaca1',
              'color': '#7c4544',
              'fontWeight': 'bold'
            },
            {
              'if': {
                  'column_id': 'violations',
                  'filter_query': '{violations} <= 0'
              },
              'backgroundColor': '#ccfbfe',
              'color': '#3c763d',
              'fontWeight': 'bold'
            },
            {
              'if': {'row_index': 'odd'},
              'backgroundColor': 'rgb(248, 248, 248)'
            }
          ]
        )

def details_violations():
  """
  :return: A Dash table containing the detail of a specific violation
  """
  return dash_table.DataTable(
          id='table-details',
          columns=[{"name": i, "id": i } for i in df_details.columns if i != 'uid'],
          data=df_details.to_dict('records'),
          sort_action="native",
          sort_mode='multi',
          # sort_by=[{'column_id': 'name', 'direction': 'asc'}],
          filter_action="native",
          style_cell={'padding': '5px', 'textAlign': 'left', 'font-size': '16px'},    
          style_as_list_view=True,
          style_header={
              'backgroundColor': '#e6e8e6',
              'fontWeight': 'bold'
          },
          style_data={
            'whiteSpace': 'normal',
            'height': 'auto'
          },
          style_data_conditional=[
              {
                'if': {'row_index': 'odd'},
                'backgroundColor': 'rgb(248, 248, 248)'
              }
          ],
        )


def generate_layout():
  """
  
  """
  df, df_details = get_k8s_data()
  return html.Div(
    id="app-container",
    children=[
        # Banner
        html.Div(
            id="banner",
            className="banner",
            children=[html.Img(src=app.get_asset_url("gatekeeper_audit_dashboard_logo.png"))],
        ),
        # Left column
        html.Div(
            id="left-column",
            className="four columns",
            children=[description_card(), 
                html.Div(
                        id="violations_card",
                        children=[
                            html.B("Number violations in your cluster"),
                            html.P("Click on the name to see more details"),
                            html.Hr(),
                            summary_violations(),
                        ],
                    ),
            ]
            
        ),
        # Right column
        html.Div(
            id="right-column",
            className="eight columns",
            children=[
                html.Div(
                    id="details_violation_card",
                    children=[
                        html.B("Details violation"),
                        html.Hr(),
                        details_violations(),
                    ],
                ),
            ],
        ),
    ],
)

app.layout = generate_layout


@app.callback(
    Output('table-details', 'data'),
    [Input('table-violations', 'derived_virtual_row_ids'),
      Input('table-violations', 'selected_row_ids'),
      Input('table-violations', 'active_cell')])
def update_table(row_ids, selected_row_ids, active_cell):
  if active_cell is None:
    return []
  active_row_id = active_cell['row_id'] if active_cell else None
  filtered_df = df_details[df_details.uid == active_row_id]
    
  return filtered_df.to_dict('records')

if __name__ == '__main__':
  debug = os.environ.get('DEBUG') or True
  app.run_server(debug=debug)