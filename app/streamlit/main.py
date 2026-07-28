# %%
import pandas as pd
import requests

import pandas as pd
import streamlit as st
from deltalake import DeltaTable

import os 
import dotenv

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


def get_id_predictions(values):
    data = {
        "values": values.to_dict(orient='records')
    }

    resp = requests.post(f"{URI_API}/predict", json=data)
    return resp.json().get("predictions")


@st.cache_data(ttl="1d")
def get_predictions():

    data = (
        DeltaTable(DELTA_TABLE_PATH_SILVER)
        .to_pyarrow_table()
        .to_pandas()
        )
    
    data = data.fillna(value=-10000)
    data['dt_ref'] = data['dt_ref'].astype('string')
    data['id'] = (
        data['dt_ref'] 
        + '_' 
        + data['DriverId']
        )
    data['Year'] = pd.to_datetime(data['dt_ref']).dt.year
    
    df = get_id_predictions(data)
    df = (pd.DataFrame(df)
          .T
          .reset_index()
          .rename(
              columns={"index": "id", "1": "prob_win"})
          )
    
    df = pd.merge(data, df, on='id')

    results = (
        DeltaTable(DELTA_TABLE_PATH_BRONZE)
        .to_pyarrow_table()
        .to_pandas()
        .drop_duplicates(subset=["DriverId"])
        )

    results = results[['DriverId', 'TeamName',
                       'TeamColor', 'FullName' ]]
    
    results['TeamColor'] = results['TeamColor'].apply(format_color)
    
    return pd.merge(df, results, on='DriverId')        


def main() -> None:
    st.set_page_config(page_title="F1 Data", page_icon="📊", layout="wide")
    st.markdown("# :checkered_flag: F1 Data ")
    data = get_predictions()

    # st.dataframe(data)
    
    drivers_data = (data[['DriverId', 'FullName']]
                    .sort_values(["DriverId", "FullName"])
                    .drop_duplicates(subset=['DriverId'], keep='first')
                    .dropna()
                    )

    most_prob = (data
                 .sort_values(by=['dt_ref', 'prob_win'], ascending=False)
                 .head(5)
                 )

    
    driver_selected = st.multiselect(":racing_car: Driver: ",
                                     options=drivers_data['FullName'],
                                     default=most_prob['FullName'],
                                     )


    year_selected = st.multiselect(":calendar: Season: ",
                                   options=data['Year'].unique(),
                                   default=data['Year'].max(),
                                   )

    data_filter = data[data["FullName"].isin(driver_selected)]
    data_filter = data_filter[data_filter['Year'].isin(year_selected)]


    data_chart = (data_filter
                  .pivot_table(index='dt_ref', columns='FullName', values='prob_win')
                  .reset_index()
                  )
    drivers_select = data_chart.columns.tolist()[1:]
    
    team_colors = (
        data_filter[['FullName', 'TeamColor']].drop_duplicates("FullName")
        .set_index("FullName")
        .reindex(drivers_select)["TeamColor"]
        .tolist()
        )
    
    
    column_config={i: st.column_config.NumberColumn(i, format="percent") for i in data_chart.columns[1:]}
    column_config["dt_ref"] = st.column_config.DateColumn("Data Predict")


    graphs, tables = st.tabs(["Graphic", "Tables"])

    with graphs:
        st.line_chart(data_chart,
                    x='dt_ref',
                    y=drivers_select,
                    y_label="Champion Win Prob.",
                    x_label='Post-Race Date',
                    color=team_colors,
                    )

    with tables:
        st.markdown("Driver predict")
        st.dataframe(data_chart, column_config=column_config)

        st.markdown("Full table")
        st.dataframe(data_filter)


# %%
if __name__ == "__main__":
    main()

# %%
