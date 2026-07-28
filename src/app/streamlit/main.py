# %%
import pandas as pd
import requests

import pandas as pd
import streamlit as st
from deltalake import DeltaTable

URI_API = "http://localhost:5002"

class Driver:

    def __init__(self, DriverId, driver_name):
        self.DriverId = DriverId
        self.driver_name = driver_name

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
        DeltaTable("data/silver/tb_abt")
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
    df = pd.DataFrame(df).T.reset_index().rename(
        columns={"index": "id", "1": "prob_win"})
    
    df = pd.merge(data, df, on='id')

    results = (
        DeltaTable("data/bronze/results")
        .to_pyarrow_table()
        .to_pandas()
        .drop_duplicates(subset=["DriverId"])
        )

    results = results[['DriverId', 'TeamName',
                       'TeamColor', 'FullName' ]]
    
    results['TeamColor'] = results['TeamColor'].apply(format_color)
    
    return pd.merge(df, results, on='DriverId')        


def main() -> None:
    st.set_page_config(page_title="F1 Data App", page_icon=":racing_car:", layout="wide")
    st.markdown("# :checkered_flag: F1 Data ")
    data = get_predictions()


    

    # st.dataframe(data)
    
    # drivers = [Driver(i['DriverId'], i['FullName_correct']) for i in drivers_data.to_dict(orient='records')]

    # most_prob = (data[data['dt_ref']==data['dt_ref'].max()].sort_values(by='prob_win', ascending=False)
                                                        # .head(3))

    # drivers_default = [i for i in drivers if i.DriverId in most_prob['DriverId'].tolist()]
    
    # max_year = data['Year'].max()
    
    # top_5_drivers = (
    #     data.loc[data['Year'].eq(max_year)]
    #     .groupby("DriverId", as_index=False)["prob_win"]
    #     .max()
    #     .nlargest(5, "prob_win")
    #     ["DriverId"]
    #     .tolist()
    # )

    # driver_selected = st.multiselect(
    #     ":racing_car: Driver: ", 
    #     options=data['DriverId'].unique(),
    #     # default=top_5_drivers
    #     default=drivers_default
    #     )
    
    # year_selected = st.multiselect(
    #     ":calendar: Season: ", 
    #     options=data['Year'].unique(),
    #     default=max_year
    #     )

    # data_filter = data[data["DriverId"].isin([driver_selected])]
    # data_filter = data_filter[data_filter['Year'].isin(year_selected)]


    # colors = (data_filter[['DriverId','dt_ref','TeamColor']]
    #           .sort_values(by=['DriverId', 'dt_ref'], ascending=[True, False])
    #           .drop_duplicates(subset=['DriverId'], keep="first")['TeamColor'].tolist())


    # data_chart = (data_filter.pivot_table(index='dt_ref', columns='DriverId', values='prob_win')
    #                         .reset_index())


    # column_config={i: st.column_config.NumberColumn(i, format="percent") for i in data_chart.columns[1:]}
    # column_config["dt_ref"] = st.column_config.DateColumn("Data Predict")


    # graphs, tables = st.tabs(["Graphic", "Table"])


    # with graphs:
    #     st.line_chart(data_chart,
    #                 x='dt_ref',
    #                 y='Driver',
    #                 y_label="Championship Win Probability",
    #                 x_label='Post-Race Date',
    #                 # color=colors,
    #                 )


    # with tables:
    #     st.dataframe(data_chart, column_config=column_config)

    #     st.markdown("Analytical Base Table")
    #     st.dataframe(data_filter)
    
    drivers_data = (data[['DriverId', 'FullName']].sort_values(["DriverId", "FullName"])
                                                        .drop_duplicates(subset=['DriverId'], keep='first')
                                                        .dropna())

    drivers = [Driver(i['DriverId'], i['FullName']) for i in drivers_data.to_dict(orient='records')]

    most_prob = (data[data['dt_ref']==data['dt_ref'].max()].sort_values(by='prob_win', ascending=False)
                                                        .head(5))

    drivers_default = [i for i in drivers if i.DriverId in most_prob['DriverId'].tolist()]


    driver_selected = st.multiselect("Pilotos",
                                    options=drivers,
                                    format_func=lambda x: x.driver_name,
                                    default=drivers_default,
                                    )


    year_selected = st.multiselect("Temporada",
                                options=data['Year'].unique(),
                                default=data['Year'].max(),
                                )


    data_filter = data[data["DriverId"].isin([i.DriverId for i in driver_selected])]
    data_filter = data_filter[data_filter['Year'].isin(year_selected)]


    colors = (data_filter[['FullName','dt_ref','TeamColor']].sort_values(by=['FullName', 'dt_ref'], ascending=[True, False])
                                                                    .drop_duplicates(subset=['FullName'], keep="first")
                                                            ['TeamColor'].tolist())


    data_chart = (data_filter.pivot_table(index='dt_ref', columns='FullName', values='prob_win')
                            .reset_index())


    column_config={i: st.column_config.NumberColumn(i, format="percent") for i in data_chart.columns[1:]}
    column_config["dt_ref"] = st.column_config.DateColumn("Data Predição")


    graphs, tables = st.tabs(["Gráfico", "Tabelas"])


    with graphs:
        st.line_chart(data_chart,
                    x='dt_ref',
                    y=data_chart.columns.tolist()[1:],
                    y_label="Prob. Vitória Campeonato",
                    x_label='Data Pós Corrida',
                    color=colors,
                    )


    with tables:
        st.dataframe(data_chart, column_config=column_config)

        st.markdown("Analytical Base Table")
        st.dataframe(data_filter)


# %%
if __name__ == "__main__":
    main()

# %%
