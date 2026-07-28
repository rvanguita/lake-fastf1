import subprocess
import sys
from pathlib import Path


from src.raw import main as raw_data
from consolidate_data import main as bronze_data
from silver_data import main as silver_data


def main() -> None:
    print("Init Collect")
    raw_data()
    print("Finish Collect")

    print("Init Consolidate")
    bronze_data()
    print("Finish Consolidate")

    print("Init Create tables")
    silver_data()
    print("Finish Create tables")


if __name__ == "__main__":
    main()
