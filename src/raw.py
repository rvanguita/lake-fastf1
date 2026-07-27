# %%
import os
import time

import fastf1
import argparse
import pandas as pd
from datetime import date, datetime

from pathlib import Path

from rich.progress import track

import dotenv

dotenv.load_dotenv()  # Load environment variables from .env file

fastf1.set_log_level(level=100)

CURRENT_YEAR = datetime.now().year


class ExtractData:
    def __init__(
        self, years: list[int], reload_data: bool,
        identifiers: list[str], base_path: str = os.getenv("PATH_RAW")
    ) -> None:

        self.years = years
        self.identifiers = identifiers
        self.reload_data = reload_data
        self.path_save_data = f"{base_path}/results"

        os.makedirs(self.path_save_data, exist_ok=True)

    def get_data(self, year: int, gp: int, identifier: str) -> pd.DataFrame:
        try:
            session = fastf1.get_session(year, gp, identifier)
        except ValueError as err:
            empty = pd.DataFrame()
            return empty

        session.load()
        df = self.prepare_data(session)

        return df

    def prepare_data(self, session):
        df = session.results
        df["Year"] = session.date.year
        df["Date"] = session.date
        df["Mode"] = session.name
        df["RoundNumber"] = session.event["RoundNumber"]
        df["OfficialEventName"] = session.event["OfficialEventName"]
        df["EventName"] = session.event["EventName"]
        df["Country"] = session.event["Country"]
        df["Location"] = session.event["Location"]

        df["Date"] = df["Date"].astype('datetime64[us]')
        columns_names = ['Q1', 'Q2', 'Q3', 'Time']
        for i in columns_names:
            df[i] = df[i].dt.total_seconds()
        return df

    def process_data(self, year: int, gp: int, identifier: str) -> bool:
        filename = f"{self.path_save_data}/{year}_{(gp):02}_{identifier}.parquet"
        if (Path(filename).is_file() and
                not self.reload_data):
            return False

        df = self.get_data(year, gp, identifier)
        if df.empty:
            return False

        self.save_data_parquet(df, filename)
        time.sleep(1)
        return True

    def save_data_parquet(self, df: pd.DataFrame, filename: str) -> None:
        df.to_parquet(filename, index=False)

    def process_years(self) -> None:
        for year in track(self.years, description=f"Processing year"):
            self.process_identifiers(year)
            time.sleep(10)

    def process_identifiers(self, year: int) -> None:
        for identifier in self.identifiers:
            for gp in range(1, 30):

                ok = self.process_data(year, gp, identifier)

                if (not ok and
                        identifier == 'R'):
                    return


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=CURRENT_YEAR)
    parser.add_argument("--identifiers", nargs='*', default=['R', 'S'])
    parser.add_argument("--reload_year", default=False)
    parser.add_argument("--reload_data", default=False)
    args = parser.parse_args()

    years = [args.year]
    if args.reload_year:
        years = [i for i in range(2026, args.year+1)]

    extract_data = ExtractData(
        years=years, reload_data=args.reload_data,
        identifiers=args.identifiers)
    print()
    extract_data.process_years()


# %%
if __name__ == "__main__":
    main()

# %%
