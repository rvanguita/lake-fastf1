# %%
import pandas as pd
import requests

import pandas as pd
import streamlit as st
from deltalake import DeltaTable

import os 

<<<<<<< Updated upstream
dotenv.load_dotenv()

URI_API = f"http://api-driver-champion:{os.getenv("API_PORT")}"
DELTA_TABLE_PATH_SILVER = os.environ["DELTA_TABLE_PATH_SILVER"]
DELTA_TABLE_PATH_BRONZE = os.environ["DELTA_TABLE_PATH_BRONZE"]
def format_color(x:str):
    if x is None:
        return "#ffffff"

    if x.startswith("#"):
        return x.lower()
    
    return f"#{x}".lower()
=======
URI_API = f"http://api-driver-champion:{os.environ["API_PORT"]}"

TABLE_PATH_SILVER = os.environ["TABLE_PATH_SILVER"]
TABLE_PATH_BRONZE = os.environ["TABLE_PATH_BRONZE"]


def format_color(color: str | None) -> str:
    if color is None:
        return "#ffffff"

    color = color.strip()

    if not color or color == "#":
        return "#ffffff"

    if color.startswith("#"):
        return color.lower()

    return f"#{color.lower()}"
>>>>>>> Stashed changes


def get_id_predictions(values):
    data = {
        "values": values.to_dict(orient='records')
    }

    resp = requests.post(f"{URI_API}/predict", json=data)
    predict =  resp.json().get("predictions")

    predict = (pd.DataFrame(predict)
               .T
               .reset_index()
               .rename(
                columns={"index": "id", 
                        "1": "prob_win"
                        })
            )
    return predict


@st.cache_data(ttl="1d",
               show_spinner="Loading predictions...",)
def get_predictions():

<<<<<<< Updated upstream
    data = (
        DeltaTable(DELTA_TABLE_PATH_SILVER)
=======
    data_base = (
        DeltaTable(TABLE_PATH_SILVER)
>>>>>>> Stashed changes
        .to_pyarrow_table()
        .to_pandas()
        ).fillna(value=-10000)

<<<<<<< Updated upstream
    results = (
        DeltaTable(DELTA_TABLE_PATH_BRONZE)
=======
    data_base['dt_ref'] = data_base['dt_ref'].astype('string')
    data_base['Year'] = pd.to_datetime(data_base['dt_ref']).dt.year
    
    data_base['id'] = (
        data_base['dt_ref'] 
        + '_' 
        + data_base['DriverId']
        )
    
    predict = get_id_predictions(data_base)

    df_consolidated = pd.merge(data_base, predict, on='id')

    tb_results = (
        DeltaTable(TABLE_PATH_BRONZE)
>>>>>>> Stashed changes
        .to_pyarrow_table()
        .to_pandas()
        .drop_duplicates(subset=["DriverId"])
        )
<<<<<<< Updated upstream

    results = results[['DriverId', 'TeamName',
                       'TeamColor', 'FullName' ]]
=======
    tb_results = tb_results[[
        'DriverId', 'TeamName',
        'TeamColor', 'FullName' , 'TeamId'
        ]]
>>>>>>> Stashed changes
    
    tb_results['TeamColor'] = tb_results['TeamColor'].apply(format_color)
    
<<<<<<< Updated upstream
    return pd.merge(df, results, on='DriverId')        
=======
    df_consolidated = pd.merge(df_consolidated, tb_results, on='DriverId')    
    
    df_consolidated['driver_team_id'] = (
        df_consolidated['DriverId'] 
        + '_' 
        + df_consolidated['TeamId']
        )
    
    return df_consolidated
>>>>>>> Stashed changes


def main() -> None:
    st.set_page_config(page_title="F1 Data", page_icon="📊", layout="wide")
<<<<<<< Updated upstream
    st.markdown("# :checkered_flag: F1 Data ")
    data = get_predictions()

    # st.dataframe(data)
    
    drivers_data = (data[['DriverId', 'FullName']]
                    .sort_values(["DriverId", "FullName"])
=======
    st.markdown("# :checkered_flag: F1 - Predict Champion")
    
    df = get_predictions()
    drivers_data = (df[['DriverId', 'driver_team_id', 'dt_ref']]
                    .sort_values(["dt_ref", "driver_team_id"])
>>>>>>> Stashed changes
                    .drop_duplicates(subset=['DriverId'], keep='first')
                    .dropna()
                    )

    most_prob = (df
                 .sort_values(by=['dt_ref', 'prob_win'], ascending=False)
                 .head(5)
                 )

    
<<<<<<< Updated upstream
    driver_selected = st.multiselect(":racing_car: Driver: ",
                                     options=drivers_data['FullName'],
                                     default=most_prob['FullName'],
=======
    driver_selected = st.multiselect(":racing_car: Driver Select: ",
                                     options=drivers_data['driver_team_id'],
                                     default=most_prob['driver_team_id'],
>>>>>>> Stashed changes
                                     )


    year_selected = st.multiselect(":calendar: Season Select: ",
                                   options=df['Year'].unique(),
                                   default=df['Year'].max(),
                                   )

    data_filter = data[data["FullName"].isin(driver_selected)]
    data_filter = data_filter[data_filter['Year'].isin(year_selected)]

<<<<<<< Updated upstream

    data_chart = (data_filter
                  .pivot_table(index='dt_ref', columns='FullName', values='prob_win')
                  .reset_index()
                  )
    drivers_select = data_chart.columns.tolist()[1:]
    
    team_colors = (
        data_filter[['FullName', 'TeamColor']].drop_duplicates("FullName")
        .set_index("FullName")
=======
    df_filter = df[
        df["driver_team_id"].isin(driver_selected)
        & df["Year"].isin(year_selected)
    ]
    
    df_pivot = (df_filter
                  .pivot_table(index='dt_ref', 
                               columns='driver_team_id', 
                               values='prob_win'
                               )
                  .reset_index()
                  ).sort_values(by='dt_ref', ascending=False)
    drivers_select = df_pivot.columns.tolist()[1:]
    
    team_colors = (
        df_filter[['driver_team_id', 'TeamColor']]
        .drop_duplicates("driver_team_id")
        .set_index("driver_team_id")
>>>>>>> Stashed changes
        .reindex(drivers_select)["TeamColor"]
        .tolist()
        )
    
    
<<<<<<< Updated upstream
    column_config={i: st.column_config.NumberColumn(i, format="percent") for i in data_chart.columns[1:]}
=======
    column_config={
        i: st.column_config.NumberColumn(i, format="percent") for i in df_pivot.columns[1:]
        }
    
>>>>>>> Stashed changes
    column_config["dt_ref"] = st.column_config.DateColumn("Data Predict")


    graphs, tables = st.tabs(["Graphic", "Tables"])

    with graphs:
<<<<<<< Updated upstream
        st.line_chart(data_chart,
=======
        st.line_chart(df_pivot,
>>>>>>> Stashed changes
                    x='dt_ref',
                    y=drivers_select,
                    y_label="Champion Win Prob.",
                    x_label='Post-Race Date',
                    color=team_colors,
                    )

    with tables:
        st.markdown("Driver predict")
<<<<<<< Updated upstream
        st.dataframe(data_chart, column_config=column_config)
=======
        st.dataframe(df_pivot, column_config=column_config)
>>>>>>> Stashed changes

        st.markdown("Full table")
        st.dataframe(df_filter)


# %%
if __name__ == "__main__":
    main()

# %%
