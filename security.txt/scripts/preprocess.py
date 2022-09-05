from typing import Final

import csv
import pathlib


import typer
from loguru import logger
from alive_progress import alive_bar


DOMAIN_HEADER: Final[str] = "Domain"


def main(
    magestic_path: pathlib.Path = typer.Argument(
        ..., help="Path to Magestic Million CSV file."
    ),
    out_path: pathlib.Path = typer.Argument(
        ..., help="Path to output preprocessed data to."
    ),
) -> None:
    logger.info(f"Reading from {magestic_path} and writing to {out_path}...")

    num_records = 0
    with open(magestic_path, "r") as magestic_file, open(
        out_path, "w"
    ) as out_file, alive_bar() as bar:
        reader = csv.DictReader(magestic_file)
        writer = csv.DictWriter(out_file, fieldnames=[DOMAIN_HEADER])

        writer.writeheader()
        for line in reader:
            domain = line[DOMAIN_HEADER]
            writer.writerow({DOMAIN_HEADER: domain})
            num_records += 1
            bar()
    logger.success(f"Wrote {num_records} records to {out_path}")


if __name__ == "__main__":
    typer.run(main)
